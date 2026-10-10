"""HOD-reviewed result snapshots and durable delivery queue; no network in requests."""
import hashlib
import json
import re
import textwrap
from collections import Counter

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from students.models import Student, Guardian
from .calculations import calculate_weighted_average
from .grading import grade_point_for_score
from .models import (CourseOffering, GuardianSharingPreference, ResultShareBatch,
                     ResultShareDelivery)
from .services import require_hod


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def contact(guardian, channel):
    value = (guardian.email or "").strip() if channel == "email" else guardian.phone_number.strip()
    if channel == "email":
        try:
            validate_email(value)
        except ValidationError:
            return "", "invalid_email"
    elif not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
        return "", "international_phone_required"
    return value, ""


def report_for(student, session, semester):
    # CGPA is cumulative as of the selected period, excluding later results.
    results = list(student.results.select_related("grading_scale", "offering__course",
        "offering__academic_session").order_by("pk"))
    cutoff = (session.name, 0 if semester == "harmattan" else 1)
    relevant = [r for r in results if (r.offering.academic_session.name,
        0 if r.offering.semester == "harmattan" else 1) <= cutoff]
    selected = [r for r in relevant if r.offering.academic_session_id == session.pk
                and r.offering.semester == semester]
    if not selected:
        raise ValidationError("No recorded results for the selected semester.")
    gpa, cgpa = calculate_weighted_average(selected), calculate_weighted_average(relevant)
    records = [{"id": r.pk, "course": r.offering.course.code, "title": r.offering.course.title,
        "session": r.offering.academic_session.name, "semester": r.offering.semester,
        "attempt": r.attempt_number, "score": str(r.score), "units": r.credit_units,
        "scale": r.grading_scale_id, "grade_point": str(grade_point_for_score(r.score,
            grading_scale=r.grading_scale))} for r in relevant]
    selected_ids = {r.pk for r in selected}
    lines = [f"Student: {student.full_name} ({student.identifier_value})",
             f"Results: {session.name} / {semester}"]
    for row in records:
        if row["id"] in selected_ids:
            lines.append(f'{row["course"]}: score {row["score"]}, units {row["units"]}, '
                         f'grade point {row["grade_point"]}, attempt {row["attempt"]}')
    lines += [f"Semester GPA: {gpa}", f"Cumulative CGPA through this period: {cgpa}",
              "Verified recorded results; this is not certification of complete academic history."]
    return {"gpa": str(gpa), "cgpa": str(cgpa), "records": records, "text": "\n".join(lines)}


def build_preview(students, session, semester, channels):
    preview, deliveries = [], []
    for student in students:
        error, report = "", None
        try:
            report = report_for(student, session, semester)
        except ValidationError:
            error = "results_missing_or_unverified"
        item = {"student_id": str(student.pk), "name": student.full_name,
                "identifier": student.identifier_value, "report": report,
                "diagnostic_code": error, "recipients": []}
        guardians = list(student.guardians.order_by("pk"))
        if not guardians:
            item["diagnostic_code"] = error or "no_guardians"
        seen = set()
        for guardian in guardians:
            preference = GuardianSharingPreference.objects.filter(guardian=guardian).first()
            for channel in channels:
                destination, invalid = contact(guardian, channel)
                allowed = bool(preference and getattr(preference, channel + "_enabled"))
                body = report["text"] if report else ""
                if channel == "whatsapp":
                    body = " ".join(body.split())
                reason = error or ("sharing_not_enabled" if not allowed else invalid)
                key = (channel, destination.casefold() if channel == "email" else destination)
                if not reason and key in seen:
                    reason = "duplicate_contact"
                if not reason:
                    seen.add(key)
                parts = (textwrap.wrap(body, width=850) or [""]) if channel == "whatsapp" else [body]
                if channel == "whatsapp" and len(parts) > 1:
                    parts = [f"Report part {i}/{len(parts)}: {part}" for i, part in enumerate(parts, 1)]
                recipient = {"parts": len(parts), "guardian_id": str(guardian.pk), "guardian_name": guardian.full_name,
                    "channel": channel, "destination": destination,
                    "preference_updated_at": preference.updated_at.isoformat() if preference else None,
                    "diagnostic_code": reason}
                item["recipients"].append(recipient)
                for number, part in enumerate(parts, 1):
                    deliveries.append({"student": student, "guardian": guardian, "channel": channel,
                        "destination": destination, "body": part, "part_number": number,
                        "subject": f"Student results: {session.name} / {semester}",
                        "diagnostic_code": reason, "status": "skipped" if reason else "draft"})
        preview.append(item)
    return preview, deliveries


def lock_students(ids):
    students = list(Student.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    if len(students) != len(ids):
        raise ValidationError("One or more selected students do not exist.")
    return students


@transaction.atomic
def create_preview(*, user, request_id, student_ids, academic_session, semester, channels):
    require_hod(user)
    ids, channels = sorted(str(i) for i in student_ids), sorted(channels)
    students = lock_students(ids)
    existing = ResultShareBatch.objects.filter(pk=request_id).first()
    if existing:
        if (existing.created_by_id != user.pk or existing.student_ids != ids or
                existing.channels != channels or existing.academic_session_id != academic_session.pk
                or existing.semester != semester):
            raise ValidationError("This request_id belongs to a different request.")
        return existing
    preview, deliveries = build_preview(students, academic_session, semester, channels)
    try:
        with transaction.atomic():
            batch = ResultShareBatch.objects.create(id=request_id, created_by=user,
                academic_session=academic_session, semester=semester, student_ids=ids,
                channels=channels, preview=preview, history_digest=digest(preview))
    except IntegrityError:
        # A concurrent request with a reused UUID can have a disjoint student set.
        raise ValidationError("This request_id already exists. Refresh the original request.") from None
    ResultShareDelivery.objects.bulk_create([ResultShareDelivery(batch=batch, **row) for row in deliveries])
    return batch


@transaction.atomic
def queue_batch(*, user, batch, expected_digest):
    require_hod(user)
    batch = ResultShareBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.history_digest != expected_digest:
        raise ValidationError("The preview digest does not match.")
    if batch.queued_at:
        return batch  # Repeated clicks do not create or resend deliveries.
    students = lock_students(batch.student_ids)
    current, _ = build_preview(students, batch.academic_session, batch.semester, batch.channels)
    if digest(current) != batch.history_digest:
        raise ValidationError("Results or guardian details changed. Create a fresh preview.")
    pending = batch.deliveries.filter(status="draft")
    if not pending.exists():
        raise ValidationError("No eligible guardian deliveries. Review the preview diagnostics.")
    from .sharing_transport import validate_transport
    for channel in pending.values_list("channel", flat=True).distinct():
        validate_transport(channel)
    pending.update(status="queued")
    batch.queued_at = timezone.now()
    batch.save(update_fields=["queued_at"])
    return batch


@transaction.atomic
def set_preference(*, user, guardian, email_enabled, whatsapp_enabled, evidence):
    require_hod(user)
    Student.objects.select_for_update().get(pk=guardian.student_id)
    if not evidence.strip():
        raise ValidationError("Record the basis of guardian sharing permission or withdrawal.")
    preference, _ = GuardianSharingPreference.objects.update_or_create(guardian=guardian,
        defaults={"email_enabled": email_enabled, "whatsapp_enabled": whatsapp_enabled,
                  "evidence": evidence, "updated_by": user})
    return preference


@transaction.atomic
def retry_failed(*, user, batch):
    require_hod(user)
    batch = ResultShareBatch.objects.select_for_update().get(pk=batch.pk)
    failed = batch.deliveries.filter(status="failed", attempts__lt=3)
    from .sharing_transport import validate_transport
    for channel in failed.values_list("channel", flat=True).distinct():
        validate_transport(channel)
    return failed.update(status="queued", diagnostic_code="")


def batch_data(batch):
    counts = Counter(batch.deliveries.values_list("status", flat=True))
    return {"id": str(batch.pk), "history_digest": batch.history_digest,
        "queued_at": batch.queued_at, "preview": batch.preview, "counts": dict(counts),
        "deliveries": list(batch.deliveries.order_by("pk").values("id", "student_id", "guardian_id",
            "channel", "part_number", "destination", "status", "diagnostic_code", "attempts", "provider_id"))}
