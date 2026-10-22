from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from academics.current_session import current_session_name
from academics.models import CurrentAcademicSession, CourseOffering, Result
from academics.grading import grade_point_for_score
from academics.services import require_hod
from students.models import Student
from .models import (CourseStaffAssignment, CourseRoster, AttendanceSession,
                     AttendanceRecord, AttendanceEvent, AttendanceCorrection, CourseRosterApproval,
                     PendingCaptureEvent)


# Lock the selected academic-session row to serialize attendance with calendar changes.
def lock_calendar():
    # Serialize session changes with attendance writes before taking course locks.
    CurrentAcademicSession.objects.select_for_update().get(pk=1)


# Enforce current-session, staff, permission, and active assignment access.
def require_course(user, offering, action):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        raise PermissionDenied("Active staff access is required.")
    if user.is_superuser:
        return
    if offering.academic_session.name != current_session_name() or not user.has_perm("attendance." + action):
        raise PermissionDenied("Attendance permission for the current academic session is required.")
    if not CourseStaffAssignment.objects.select_for_update().filter(offering=offering, staff=user, is_active=True).exists():
        raise PermissionDenied("You are not assigned to this course offering.")


# Reject operations against offerings outside the configured academic session.
def current_offering(offering):
    if offering.academic_session.name != current_session_name():
        raise ValidationError("Select an offering in the current academic session.")


# Suggest active undergraduates at the course level or with a latest failed attempt.
def roster_candidates(offering):
    active = Student.objects.filter(is_active=True, academic_status="undergraduate")
    reasons = {str(pk): ["current_level"] for pk in active.filter(current_level=offering.level).values_list("pk", flat=True)}
    latest = {}
    results = Result.objects.filter(offering__course=offering.course, student__in=active,
        is_verified=True, score__isnull=False).select_related("offering__academic_session", "grading_scale")
    target = (offering.academic_session.name, 0 if offering.semester == "harmattan" else 1)
    for result in results:
        period = (result.offering.academic_session.name, 0 if result.offering.semester == "harmattan" else 1)
        if period >= target:
            continue
        key = (*period, result.attempt_number, result.pk)
        sid = str(result.student_id)
        if sid not in latest or key > latest[sid][0]:
            latest[sid] = (key, result)
    for sid, (_, result) in latest.items():
        if grade_point_for_score(result.score, grading_scale=result.grading_scale) == 0:
            reasons.setdefault(sid, []).append("latest_verified_attempt_failed")
    return [{"student_id": str(s.pk), "full_name": s.full_name,
             "identifier_value": s.identifier_value, "reasons": reasons[str(s.pk)]}
            for s in active.filter(pk__in=reasons).order_by("full_name", "pk")]


# Assign or deactivate staff for an offering after HOD authorization.
@transaction.atomic
def assign_staff(*, user, offering, staff, is_active):
    require_hod(user)
    lock_calendar()
    offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)
    if is_active and (not staff.is_staff or not staff.is_active):
        raise ValidationError("Select an active staff account.")
    assignment, _ = CourseStaffAssignment.objects.update_or_create(offering=offering, staff=staff,
        defaults={"is_active": is_active})
    return assignment


# Confirm a unique eligible roster against its expected revision and archive it.
@transaction.atomic
def confirm_roster(*, user, offering, student_ids, expected_revision):
    require_hod(user)
    lock_calendar()
    offering = CourseOffering.objects.select_for_update().select_related("academic_session").get(pk=offering.pk)
    current_offering(offering)
    if not 1 <= len(student_ids) <= 1000 or len(student_ids) != len(set(student_ids)):
        raise ValidationError("Provide a nonempty list of unique student IDs.")
    students = list(Student.objects.select_for_update().filter(pk__in=student_ids,
        is_active=True, academic_status="undergraduate").order_by("pk"))
    if len(students) != len(student_ids):
        raise ValidationError("Every roster member must be an active undergraduate student.")
    roster = CourseRoster.objects.select_for_update().filter(offering=offering).first()
    if (roster.revision if roster else 0) != expected_revision:
        raise ValidationError("The roster changed. Refresh its revision before confirming.")
    if roster is None:
        roster = CourseRoster.objects.create(offering=offering, confirmed_by=user)
    else:
        roster.revision += 1
        roster.confirmed_by = user
        roster.save()
    roster.students.set(students)
    CourseRosterApproval.objects.create(offering=offering, revision=roster.revision,
        student_ids=sorted(str(student.pk) for student in students), confirmed_by=user)
    return roster


# Open a session using a snapshot of the offering's confirmed roster.
@transaction.atomic
def open_session(*, user, offering, title, starts_at, ends_at):
    lock_calendar()
    offering = CourseOffering.objects.select_for_update().select_related("academic_session").get(pk=offering.pk)
    require_course(user, offering, "manage_attendance")
    current_offering(offering)
    if ends_at <= starts_at:
        raise ValidationError("The end time must follow the start time.")
    roster = CourseRoster.objects.select_for_update().filter(offering=offering).first()
    if roster is None:
        raise ValidationError("The HOD must confirm the course roster first.")
    return AttendanceSession.objects.create(offering=offering, title=title, starts_at=starts_at,
        ends_at=ends_at, opened_by=user, roster_revision=roster.revision,
        student_ids=sorted(str(pk) for pk in roster.students.values_list("pk", flat=True)))


# Close an open attendance session while preserving who closed it and when.
@transaction.atomic
def close_session(*, user, session):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "manage_attendance")
    if session.status == "open":
        session.status, session.closed_by, session.closed_at = "closed", user, timezone.now()
        session.save(update_fields=["status", "closed_by", "closed_at"])
    return session


# Record a manual check-in idempotently while enforcing session eligibility.
@transaction.atomic
def record_manual(*, user, session, student, event_id, reason):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "record_attendance")
    reason = reason.strip()
    if not reason:
        raise ValidationError("A manual attendance reason is required.")
    if PendingCaptureEvent.objects.filter(pk=event_id).exists():
        raise ValidationError("This event ID is reserved for pending capture evidence.")
    event = AttendanceEvent.objects.filter(pk=event_id).first()
    if event:
        if (event.session_id, event.student_id, event.actor_id, event.reason) != (session.pk, student.pk, user.pk, reason):
            raise ValidationError("This event ID was already used for different data.")
        return event, True
    if session.status != "open" or not session.starts_at <= timezone.now() <= session.ends_at:
        raise ValidationError("The attendance session is not open within its recording window.")
    student = Student.objects.select_for_update().get(pk=student.pk)
    if str(student.pk) not in session.student_ids or not student.is_active or student.academic_status != "undergraduate":
        raise ValidationError("The student is not eligible for this session.")
    record, created = AttendanceRecord.objects.get_or_create(session=session, student=student,
        defaults={"recorded_by": user, "reason": reason})
    event = AttendanceEvent.objects.create(pk=event_id, session=session, student=student,
        actor=user, reason=reason, duplicate=not created)
    return event, False


# Change an attendance status and append an audit record of the correction.
@transaction.atomic
def correct_record(*, user, record, status, reason):
    lock_calendar()
    record = AttendanceRecord.objects.select_for_update().select_related("session__offering__academic_session").get(pk=record.pk)
    require_course(user, record.session.offering, "correct_attendance")
    reason = reason.strip()
    if status not in ("present", "absent") or not reason:
        raise ValidationError("Provide a valid status and a correction reason.")
    if status == record.status:
        raise ValidationError("Select a different attendance status.")
    AttendanceCorrection.objects.create(record=record, previous_status=record.status,
        status=status, actor=user, reason=reason)
    record.status = status
    record.save(update_fields=["status"])
    return record
