"""Audited formal exemptions without rewriting present/absent evidence."""
from django.core.exceptions import ValidationError
from django.db import transaction
from students.models import Student
from .models import AttendanceSession, AttendanceExcusal, AttendanceExcusalAction, CourseRoster
from .services import lock_calendar, require_course


@transaction.atomic
def decide_excusal(*, user, session, student, event_id, is_excused, reason, retrospective=False):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "correct_attendance")
    student = Student.objects.select_for_update().get(pk=student.pk)
    reason = reason.strip()
    outside_snapshot = str(student.pk) not in session.student_ids
    if type(retrospective) is not bool or retrospective != outside_snapshot:
        raise ValidationError("Use retrospective=true only for a student outside the meeting's historical roster.")
    if type(is_excused) is not bool or not reason or len(reason) > 1000:
        raise ValidationError("Supply a formal grant/revocation decision and a reason.")
    previous = AttendanceExcusalAction.objects.select_related("excusal").filter(pk=event_id).first()
    if previous:
        if (previous.excusal.session_id, previous.excusal.student_id, previous.actor_id,
                previous.is_excused, previous.reason, previous.excusal.retrospective) != (
                session.pk, student.pk, user.pk, is_excused, reason, retrospective):
            raise ValidationError("This excusal event ID already belongs to another decision.")
        return previous, True
    excusal = AttendanceExcusal.objects.select_for_update().filter(session=session, student=student).first()
    if excusal and excusal.retrospective != retrospective:
        raise ValidationError("An existing excusal cannot switch historical eligibility scope.")
    was_excused = excusal.is_excused if excusal else False
    if was_excused == is_excused:
        raise ValidationError("Select a different formal excusal state.")
    eligibility_revision = session.roster_revision
    if retrospective:
        if is_excused:
            roster = CourseRoster.objects.select_for_update().filter(offering=session.offering).first()
            if not roster or roster.revision <= session.roster_revision or not roster.students.filter(pk=student.pk).exists():
                raise ValidationError("A retrospective excuse requires membership in the current later HOD-approved course roster.")
            eligibility_revision = roster.revision
        else:
            # Revoking a previously authorised exception remains possible after
            # later roster removal; this never grants historical membership.
            eligibility_revision = excusal.eligibility_roster_revision
    if excusal is None:
        excusal = AttendanceExcusal.objects.create(session=session, student=student,
            is_excused=is_excused, retrospective=retrospective, eligibility_roster_revision=eligibility_revision,
            reviewed_by=user, reason=reason)
    else:
        excusal.is_excused, excusal.reviewed_by, excusal.reason = is_excused, user, reason
        excusal.eligibility_roster_revision = eligibility_revision
        excusal.save(update_fields=["is_excused", "reviewed_by", "reviewed_at", "reason", "eligibility_roster_revision"])
    action = AttendanceExcusalAction.objects.create(pk=event_id, excusal=excusal,
        previous_is_excused=was_excused, is_excused=is_excused, actor=user, reason=reason,
        eligibility_roster_revision=eligibility_revision)
    return action, False


def excusal_snapshot(session):
    return [{"student_id": str(row.student_id), "is_excused": row.is_excused,
             "retrospective": row.retrospective, "historical_roster_member": not row.retrospective,
             "eligibility_roster_revision": row.eligibility_roster_revision,
             "reviewed_by": row.reviewed_by_id, "reviewed_at": row.reviewed_at.isoformat(),
             "reason": row.reason,
             "action_ids": sorted(str(pk) for pk in row.actions.values_list("pk", flat=True))}
            for row in session.excusals.order_by("student_id")]
