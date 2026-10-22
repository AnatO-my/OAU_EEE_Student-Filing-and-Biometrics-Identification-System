"""Reviewed imports with immutable sources, current authorization and atomic receipts."""
import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import AdviserAssignment
from academics.current_session import current_session_name
from academics.models import AcademicSession, Course, CourseOffering, CurrentAcademicSession, GradingScale, Result
from academics.services import create_result, update_result_score
from students.identity import identifier_is_unavailable, identifier_key, resolve_student_identifier
from students.models import Student
from students.services import create_student

from .format import parse_csv, validate_identity, roster_values, result_values
from .models import ImportBatch, ImportChange, ImportMutex


class ImportConflict(ValidationError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def require_access(user, kind):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        raise PermissionDenied("An active staff account is required.")
    required = ["students.view_student"]
    required += (["students.add_student"] if kind == "roster" else ["academics.view_result", "academics.add_result"])
    if any(not user.has_perm(permission) for permission in required):
        raise PermissionDenied("You do not have permission for this import.")
    if not user.is_superuser and not current_session_name():
        raise PermissionDenied("The current academic session is not configured.")


def fresh_user(user, lock=False):
    if not user.is_authenticated:
        raise PermissionDenied("An active staff account is required.")
    query = get_user_model().objects
    if lock:
        query = query.select_for_update()
    try:
        return query.get(pk=user.pk)
    except get_user_model().DoesNotExist:
        raise PermissionDenied("An active staff account is required.") from None


def access_context(user, kind):
    require_access(user, kind)
    session = current_session_name()
    levels = list(AdviserAssignment.objects.filter(staff=user, academic_session=session, is_active=True).order_by("level").values_list("level", flat=True)) if not user.is_superuser else []
    return {"session": session, "levels": levels, "permissions": sorted(user.get_all_permissions()), "is_superuser": user.is_superuser}


def visible(student, user, context):
    return user.is_superuser or student.current_level in context["levels"]


def name_key(value):
    return " ".join(value.split()).casefold()


def build_preview(user, kind, rows):
    context = access_context(user, kind)
    output, states, seen = [], [], set()
    summary = {"total": len(rows), "new_students": 0, "new_results": 0, "unchanged": 0, "corrections": 0, "blocked": 0}
    for source in rows:
        row = {**source, "action": "blocked", "code": "", "message": ""}
        state = {}
        def block(code, message):
            row.update(action="blocked", code=code, message=message)
        invalid = validate_identity(source)
        if invalid:
            block(*invalid)
        else:
            student = resolve_student_identifier(source["identifier_type"], source["identifier_value"])
            identity = identifier_key(source["identifier_value"])
            if (student and not visible(student, user, context)) or (student is None and identifier_is_unavailable(source["identifier_value"])):
                block("unavailable_student", "No student is available within your current access. Ask the HOD to review this identifier.")
            else:
                if student:
                    row["student_id"] = str(student.pk)
                    state["student"] = {"id": str(student.pk), "identifier_type": student.identifier_type,
                        "identifier_value": student.identifier_value, "full_name": student.full_name,
                        "surname": student.surname, "phone_number": student.phone_number,
                        "admission_year": student.admission_year, "mode_of_admission": student.mode_of_admission,
                        "current_level": student.current_level, "academic_status": student.academic_status, "is_active": student.is_active}
                try:
                    if kind == "roster":
                        values = roster_values(source)
                        key = (str(student.pk) if student else identity,)
                        if student:
                            conflicts = [field for field in ("admission_year", "mode_of_admission", "current_level") if getattr(student, field) != values[field]]
                            if name_key(student.full_name) != name_key(values["full_name"]):
                                conflicts.append("full_name")
                            for field in ("surname", "phone_number"):
                                if values[field] and getattr(student, field) and name_key(values[field]) != name_key(getattr(student, field)):
                                    conflicts.append(field)
                            if conflicts:
                                block("identity_conflict", "Existing profile differs in " + ", ".join(conflicts) + ". Review the student record; this import never overwrites biodata.")
                            else:
                                row.update(action="unchanged", code="existing_student", message="Existing student retained; no profile or account changes.")
                        elif not user.is_superuser and values["current_level"] not in context["levels"]:
                            block("unavailable_level", "This row is outside your current adviser assignment.")
                        else:
                            row.update(action="create_student", code="new_student", message="Create a student record only; no login account is created.")
                    else:
                        attempt, score = result_values(source)
                        key = (str(student.pk) if student else identity, source["course_code"], source["academic_session"], source["semester"], attempt)
                        if not student:
                            block("unknown_student" if user.is_superuser else "unavailable_student", "No student is available within your current access. Register the student with required biodata, then refresh this preview, or ask the HOD.")
                        elif student.academic_status == "graduated" or not student.is_active:
                            block("inactive_student", "Inactive or graduated student records require HOD review before result changes.")
                        elif source.get("full_name") and name_key(student.full_name) != name_key(source["full_name"]):
                            block("identity_conflict", "The supplied name differs from this student's profile. Review the identity before importing.")
                        else:
                            offerings = list(CourseOffering.objects.filter(course__code=source["course_code"], academic_session__name=source["academic_session"], semester=source["semester"]).select_related("grading_scale")[:2])
                            if len(offerings) != 1:
                                block("unavailable_offering", "The course offering must be configured for this exact course, session and semester.")
                            else:
                                offering = offerings[0]
                                state["offering"] = {"id": offering.pk, "credit_units": offering.credit_units, "grading_scale": offering.grading_scale_id, "published": offering.grading_scale.is_published, "bands": offering.grading_scale.bands}
                                row["offering_id"] = offering.pk
                                if not offering.grading_scale.is_published:
                                    block("unpublished_grading", "The offering requires a published grading version.")
                                else:
                                    existing = Result.objects.filter(student=student, offering=offering, attempt_number=attempt).first()
                                    state["result"] = None if existing is None else {"id": existing.pk, "score": str(existing.score) if existing.score is not None else None, "is_verified": existing.is_verified, "grading_scale": existing.grading_scale_id, "credit_units": existing.credit_units}
                                    if existing is None:
                                        row.update(action="create_result", code="new_result", message="Create an unverified result for the existing student.")
                                    elif existing.score == score:
                                        row.update(action="unchanged", code="existing_result", message="The same result and score are already recorded.")
                                    elif not user.has_perm("academics.change_result"):
                                        block("correction_permission_required", "An existing score differs. A reviewer with score-correction permission must handle it.")
                                    else:
                                        row.update(action="correction", code="score_conflict", message="Explicit approval and a reason are required. Correction clears verification.")
                                        row["existing_score"] = None if existing.score is None else str(existing.score)
                                        row["result_id"] = existing.pk
                    if key in seen:
                        block("duplicate_row", "The same student/result appears more than once in this file. Resolve duplicates before importing.")
                    seen.add(key)
                except ValidationError as error:
                    block("invalid_row", " ".join(error.messages))
        if row["action"] == "blocked":
            summary["blocked"] += 1
        else:
            summary[{"create_student": "new_students", "create_result": "new_results", "unchanged": "unchanged", "correction": "corrections"}[row["action"]]] += 1
        output.append(row)
        states.append(state)
    return {"rows": output, "summary": summary, "context": context, "states": states}


def public_batch(batch):
    return {"id": str(batch.pk), "request_id": str(batch.request_id), "kind": batch.kind,
        "filename": batch.filename, "file_sha256": batch.file_sha256, "status": batch.status,
        "revision": batch.revision, "preview_digest": batch.preview_digest,
        "summary": batch.preview["summary"], "rows": batch.preview["rows"],
        "can_commit": batch.status == "preview" and batch.preview["summary"]["blocked"] == 0,
        "receipt": batch.receipt, "created_at": batch.created_at.isoformat()}


def require_batch_access(user, batch):
    require_access(user, batch.kind)
    if batch.owner_id != user.pk:
        raise PermissionDenied("This import is not available.")
    if not user.is_superuser:
        context = access_context(user, batch.kind)
        ids = [row["student_id"] for row in batch.preview["rows"] if row.get("student_id")]
        if Student.objects.filter(pk__in=ids).exclude(current_level__in=context["levels"]).exists():
            raise PermissionDenied("An imported student is outside your current adviser assignment.")


@transaction.atomic
def create_preview(*, user, kind, request_id, filename, csv_text):
    user = fresh_user(user)
    require_access(user, kind)
    data, rows = parse_csv(kind, csv_text)
    file_hash = hashlib.sha256(data).hexdigest()
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or len(filename) > 120 or any(ord(c) < 32 for c in filename) or not filename.lower().endswith(".csv"):
        raise ValidationError("Choose a CSV filename of at most 120 characters.")
    existing = ImportBatch.objects.filter(owner=user, request_id=request_id).first()
    if existing:
        if existing.kind != kind or existing.file_sha256 != file_hash or existing.filename != filename:
            raise ImportConflict("This request ID already identifies a different file. Start a new preview request.")
        require_batch_access(user, existing)
        return existing, True
    preview = build_preview(user, kind, rows)
    try:
        with transaction.atomic():
            batch = ImportBatch.objects.create(owner=user, request_id=request_id, kind=kind, filename=filename,
                file_sha256=file_hash, source_csv=csv_text, parsed_rows=rows, preview=preview, preview_digest=digest(preview))
    except IntegrityError:
        existing = ImportBatch.objects.get(owner=user, request_id=request_id)
        if existing.kind != kind or existing.file_sha256 != file_hash or existing.filename != filename:
            raise ImportConflict("This request ID already identifies a different file. Start a new preview request.") from None
        require_batch_access(user, existing)
        return existing, True
    return batch, False


@transaction.atomic
def refresh_preview(*, user, batch_id):
    user = fresh_user(user)
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id, owner=user)
    require_batch_access(user, batch)
    if batch.status == "committed":
        raise ImportConflict("A committed import cannot be refreshed. Start a new preview for another file.")
    batch.preview = build_preview(user, batch.kind, batch.parsed_rows)
    batch.preview_digest = digest(batch.preview)
    batch.revision += 1
    batch.save(update_fields=["preview", "preview_digest", "revision", "updated_at"])
    return batch


def lock_import_context(user, batch):
    list(CurrentAcademicSession.objects.select_for_update().filter(pk=1))
    preliminary = build_preview(user, batch.kind, batch.parsed_rows)
    students = {row["student_id"] for row in preliminary["rows"] if row.get("student_id")}
    list(Student.objects.select_for_update().filter(pk__in=students).order_by("pk"))
    # Match ordinary student/result services: Student before AdviserAssignment.
    # Reversing these locks deadlocks with a concurrent manual profile edit.
    list(AdviserAssignment.objects.select_for_update().filter(staff=user).order_by("pk"))
    offerings = {row["offering_id"] for row in preliminary["rows"] if row.get("offering_id")}
    locked = list(CourseOffering.objects.select_for_update().filter(pk__in=offerings).order_by("pk"))
    list(Course.objects.select_for_update().filter(pk__in={offering.course_id for offering in locked}).order_by("pk"))
    list(AcademicSession.objects.select_for_update().filter(pk__in={offering.academic_session_id for offering in locked}).order_by("pk"))
    list(GradingScale.objects.select_for_update().filter(pk__in={offering.grading_scale_id for offering in locked}).order_by("pk"))
    list(Result.objects.select_for_update().filter(student_id__in=students, offering_id__in=offerings).order_by("pk"))


def normalize_approvals(approvals):
    result = {}
    if not isinstance(approvals, list) or len(approvals) > 1000:
        raise ValidationError("Correction approvals must be a list of at most 1000 rows.")
    for item in approvals:
        if not isinstance(item, dict) or set(item) != {"row_number", "reason"} or type(item["row_number"]) is not int:
            raise ValidationError("Each correction approval requires a row_number and reason.")
        reason = item["reason"]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000 or "\x00" in reason:
            raise ValidationError("Each approved correction requires a reason of at most 1000 characters.")
        if item["row_number"] in result:
            raise ValidationError("A correction may be approved only once.")
        result[item["row_number"]] = reason.strip()
    return result


@transaction.atomic
def commit_import(*, user, batch_id, preview_digest, correction_approvals):
    ImportMutex.objects.select_for_update().get(pk=1)
    user = fresh_user(user, lock=True)
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id, owner=user)
    require_batch_access(user, batch)
    approvals = normalize_approvals(correction_approvals)
    request = {"preview_digest": preview_digest, "correction_approvals": {str(key): value for key, value in sorted(approvals.items())}}
    if batch.status == "committed":
        if request != batch.commit_request:
            raise ImportConflict("This batch was already committed with a different review. Retrieve its receipt.")
        return batch, True
    if preview_digest != batch.preview_digest:
        raise ImportConflict("The preview changed. Refresh and review it before importing.")
    lock_import_context(user, batch)
    # Permission relationships may have changed while locks were acquired. The
    # authorization snapshot must come from fresh queries, never User caches.
    for cache in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(cache, None)
    current = build_preview(user, batch.kind, batch.parsed_rows)
    if digest(current) != batch.preview_digest:
        raise ImportConflict("Student, result, offering or authorization data changed. Refresh and review this preview again.")
    if current["summary"]["blocked"]:
        raise ImportConflict("Resolve all blocked rows before importing. No records were changed.")
    corrections = {row["row_number"] for row in current["rows"] if row["action"] == "correction"}
    if set(approvals) != corrections:
        raise ValidationError("Approve every differing score explicitly, with a reason; do not approve other rows.")
    receipt = {"import_id": str(batch.pk), "committed_at": timezone.now().isoformat(),
        "created_students": 0, "created_results": 0, "updated_results": 0, "unchanged": 0}
    try:
        with transaction.atomic():
            for row in current["rows"]:
                action = row["action"]
                if action == "unchanged":
                    receipt["unchanged"] += 1
                    continue
                before, after = {}, {}
                result = None
                if action == "create_student":
                    student = create_student(user=user, validated_data=roster_values(row))
                    after = {"student_id": str(student.pk), **roster_values(row)}
                    receipt["created_students"] += 1
                else:
                    student = Student.objects.get(pk=row["student_id"])
                    attempt, score = result_values(row)
                    if action == "create_result":
                        result = create_result(user=user, student=student, offering=CourseOffering.objects.get(pk=row["offering_id"]), score=score, attempt_number=attempt)
                        receipt["created_results"] += 1
                    else:
                        result = Result.objects.get(pk=row["result_id"])
                        before = {"score": str(result.score) if result.score is not None else None, "is_verified": result.is_verified}
                        result = update_result_score(user=user, result=result, score=score)
                        receipt["updated_results"] += 1
                    after = {"result_id": result.pk, "score": str(result.score), "is_verified": result.is_verified,
                        "offering_id": result.offering_id, "attempt_number": result.attempt_number}
                ImportChange.objects.create(batch=batch, row_number=row["row_number"], action=action,
                    student=student, result=result, before=before, after=after, reason=approvals.get(row["row_number"], ""))
    except IntegrityError:
        raise ImportConflict("An identifier or result was registered concurrently. Refresh and review this preview; no partial records were imported.") from None
    batch.status = "committed"
    batch.receipt = receipt
    batch.commit_request = request
    batch.committed_at = timezone.now()
    batch.save(update_fields=["status", "receipt", "commit_request", "committed_at", "updated_at"])
    return batch, False
