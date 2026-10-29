"""Course policies use reviewed meetings; no biometric matching is inferred."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from academics.current_session import current_session_name
from students.services import students_visible_to
from .models import (AttendancePolicyRevision, ExamExceptionDecision, CourseRoster,
                     AttendanceSession, ScannerReference)
from .services import require_course, lock_calendar
from .reconciliation import course_rates


def reason_text(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 1000:
        raise ValidationError("Supply a written reason of at most 1000 characters.")
    return reason.strip()


@transaction.atomic
def set_policy(*, user, offering, event_id, minimum_percentage, reason):
    lock_calendar()
    require_course(user, offering, "correct_attendance")
    reason = reason_text(reason)
    try:
        percentage = Decimal(str(minimum_percentage))
        if not percentage.is_finite() or not 0 <= percentage <= 100:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValidationError("Choose a threshold between 0 and 100 percent.") from None
    previous = AttendancePolicyRevision.objects.filter(event_id=event_id).first()
    if previous:
        if (previous.offering_id, previous.actor_id, previous.minimum_percentage, previous.reason) != (offering.pk, user.pk, percentage, reason):
            raise ValidationError("This policy event ID belongs to another decision.")
        return previous
    return AttendancePolicyRevision.objects.create(event_id=event_id, offering=offering,
        actor=user, minimum_percentage=percentage, reason=reason)


@transaction.atomic
def exam_exception(*, user, offering, student, event_id, enabled, reason):
    lock_calendar()
    require_course(user, offering, "correct_attendance")
    reason = reason_text(reason)
    roster = CourseRoster.objects.filter(offering=offering, students=student).exists()
    historical = any(str(student.pk) in meeting.student_ids for meeting in AttendanceSession.objects.filter(offering=offering))
    if not roster and not historical:
        raise ValidationError("Select a student belonging to this course.")
    if type(enabled) is not bool:
        raise ValidationError("Choose whether the exam exception is active.")
    previous = ExamExceptionDecision.objects.filter(event_id=event_id).first()
    if previous:
        if (previous.offering_id, previous.student_id, previous.actor_id, previous.enabled, previous.reason) != (offering.pk, student.pk, user.pk, enabled, reason):
            raise ValidationError("This exception event ID belongs to another decision.")
        return previous
    return ExamExceptionDecision.objects.create(event_id=event_id, offering=offering,
        student=student, enabled=enabled, actor=user, reason=reason)


@transaction.atomic
def eligibility(*, user, offering, student=None):
    rows = course_rates(user=user, offering=offering, finalised_only=True, student=student)
    policy = AttendancePolicyRevision.objects.filter(offering=offering).order_by("-pk").first()
    all_ids = {row["student_id"] for row in rows}
    roster = CourseRoster.objects.filter(offering=offering).first()
    if roster:
        all_ids.update(str(pk) for pk in roster.students.values_list("pk", flat=True))
    if student is not None:
        all_ids.intersection_update({str(student.pk)})
    from .reconciliation import empty_rate_row
    by_student = {row["student_id"]: row for row in rows}
    for sid in sorted(all_ids):
        row = by_student.setdefault(sid, empty_rate_row(sid))
        row.setdefault("rate_percent", None)
        decision = ExamExceptionDecision.objects.filter(offering=offering, student_id=sid).order_by("-pk").first()
        rate = Decimal(row["rate_percent"]) if row.get("rate_percent") is not None else None
        status = "unknown" if rate is None or policy is None else ("restricted" if rate < policy.minimum_percentage else "eligible")
        row.update({"basis": "current_finalised_meetings_only", "threshold": str(policy.minimum_percentage) if policy else None,
            "exam_status": "exception_approved" if decision and decision.enabled else status,
            "below_threshold": bool(rate is not None and policy and rate < policy.minimum_percentage),
            "exam_allowed": True if decision and decision.enabled else None if status == "unknown" else status == "eligible",
            "exception_reason": decision.reason if decision and decision.enabled else None})
    return list(by_student.values())


def biometric_students(user):
    from students.models import Student
    from accounts.models import AdviserAssignment
    from django.db.models import Q
    if user.is_superuser:
        return Student.objects.all()
    levels = AdviserAssignment.objects.filter(staff=user, academic_session=current_session_name(), is_active=True).values_list("level", flat=True)
    course_students = CourseRoster.objects.filter(offering__coursestaffassignment__staff=user,
        offering__coursestaffassignment__is_active=True, offering__academic_session__name=current_session_name()).values_list("students", flat=True)
    return Student.objects.filter(Q(current_level__in=levels) | Q(pk__in=course_students)).distinct()


@transaction.atomic
def enrol_reference(*, user, student, scanner_uuid, reference_id, replaces=None):
    lock_calendar()
    if not user.is_authenticated or not user.is_active or not user.is_staff or not user.has_perm("attendance.manage_biometric_reference"):
        raise PermissionDenied("Authorised biometric enrolment staff access is required.")
    if not biometric_students(user).filter(pk=student.pk).exists():
        raise PermissionDenied("This student is outside your authorised scope.")
    reference_id = reference_id.strip()
    if not reference_id or len(reference_id) > 100:
        raise ValidationError("Supply the enrolled scanner reference identifier.")
    if replaces:
        replaces = ScannerReference.objects.select_for_update().get(pk=replaces.pk)
        if replaces.student_id != student.pk:
            raise ValidationError("A replacement must belong to this student.")
        if not replaces.is_active:
            previous = ScannerReference.objects.filter(replaces=replaces, scanner_uuid=scanner_uuid, reference_id=reference_id, registered_by=user).first()
            if previous:
                return previous
            raise ValidationError("The old reference has already been disabled.")
    conflict = ScannerReference.objects.filter(scanner_uuid=scanner_uuid, reference_id=reference_id, is_active=True).first()
    if conflict and (not replaces or conflict.pk != replaces.pk):
        if conflict.student_id == student.pk and not replaces:
            return conflict
        raise ValidationError("That scanner slot is already actively assigned.")
    if replaces:
        replaces.is_active, replaces.disabled_by, replaces.disabled_at = False, user, timezone.now()
        replaces.save(update_fields=["is_active", "disabled_by", "disabled_at"])
    return ScannerReference.objects.create(student=student, scanner_uuid=scanner_uuid, reference_id=reference_id,
        registered_by=user, replaces=replaces)
