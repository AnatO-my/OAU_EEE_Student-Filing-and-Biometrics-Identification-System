"""Explicit staff reconciliation, without pretending opaque probes can be compared."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from students.models import Student
from .models import (AttendanceRecord, AttendanceSession, CaptureReview,
                     PendingCaptureEvent, ScannerReference)
from .services import lock_calendar, require_course
from .finalisation import finalisation_status


@transaction.atomic
def register_reference(*, user, session, student, scanner_uuid, reference_id):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "record_attendance")
    if not user.has_perm("attendance.manage_biometric_reference"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Authorised biometric enrolment staff access is required.")
    student = Student.objects.select_for_update().get(pk=student.pk)
    if str(student.pk) not in session.student_ids or not student.is_active:
        raise ValidationError("Select an active student in this meeting's approved roster.")
    reference_id = reference_id.strip()
    if not reference_id or len(reference_id) > 100:
        raise ValidationError("Supply the enrolled scanner reference identifier.")
    reference, _ = ScannerReference.objects.get_or_create(scanner_uuid=scanner_uuid, reference_id=reference_id, is_active=True,
        defaults={"student": student, "registered_by": user})
    if reference.student_id != student.pk:
        raise ValidationError("This scanner reference is already linked to another student.")
    return reference


@transaction.atomic
def open_review(*, user, capture, mode):
    lock_calendar()
    capture = PendingCaptureEvent.objects.select_for_update().select_related("batch__session__offering__academic_session").get(pk=capture.pk)
    require_course(user, capture.batch.session.offering, "import_pending_captures")
    if mode not in ("live", "deferred"):
        raise ValidationError("Choose live or deferred capture review.")
    review, _ = CaptureReview.objects.get_or_create(capture=capture,
        defaults={"mode": mode, "state": "flagged" if mode == "live" else "archived", "opened_by": user})
    if review.mode != mode:
        raise ValidationError("The capture review mode is already fixed.")
    return review


@transaction.atomic
def resolve_capture(*, user, capture, student, reason, timing_confirmed):
    lock_calendar()
    capture = PendingCaptureEvent.objects.select_for_update().select_related("batch__session__offering__academic_session").get(pk=capture.pk)
    session = AttendanceSession.objects.select_for_update().get(pk=capture.batch.session_id)
    require_course(user, capture.batch.session.offering, "correct_attendance")
    review = CaptureReview.objects.select_for_update().filter(capture=capture).first()
    reason = reason.strip()
    if not review:
        raise ValidationError("Choose the archived or flagged capture for review first.")
    if not reason or timing_confirmed is not True:
        raise ValidationError("Confirm the meeting timing and supply identity evidence and a resolution reason.")
    if review.state == "resolved":
        if review.student_id != student.pk or review.reason != reason:
            raise ValidationError("This capture has already been resolved with different data.")
        return review
    student = Student.objects.select_for_update().get(pk=student.pk)
    if str(student.pk) not in session.student_ids:
        raise ValidationError("The student is outside the capture's fixed meeting roster.")
    record, created = AttendanceRecord.objects.get_or_create(session=session, student=student,
        defaults={"recorded_by": user, "reason": reason})
    if not created and record.status != "present":
        raise ValidationError("Correct the existing absent record through the audited correction workflow first.")
    review.state, review.student, review.resolved_by = "resolved", student, user
    review.resolved_at, review.reason, review.record = timezone.now(), reason, record
    review.save(update_fields=["state", "student", "resolved_by", "resolved_at", "reason", "record"])
    return review


def empty_rate_row(sid):
    return {"student_id": sid, "meetings_attended": 0, "eligible_recorded_meetings": 0,
            "pending_meetings": 0, "finalised_meetings": 0, "stale_finalisation_meetings": 0,
            "excused_meetings": 0, "retrospective_excused_meetings": 0}


@transaction.atomic
def course_rates(*, user, offering, finalised_only=False, student=None):
    lock_calendar()
    if student is None:
        require_course(user, offering, "view_attendance")
    elif not user.is_authenticated or not user.is_active or student.user_id != user.pk:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Students may retrieve only their own attendance.")
    sessions = list(AttendanceSession.objects.filter(offering=offering, status="closed").prefetch_related("records", "pending_capture_batches__captures__review"))
    totals = {}
    for session in sessions:
        # Unknown identities defer the meeting unless staff explicitly reviewed
        # and finalised the current evidence while retaining those archives.
        batches = list(session.pending_capture_batches.all())
        unresolved = any(batch.recovery_review_required or not batch.captures.all() for batch in batches) or any(
            not hasattr(capture, "review") or capture.review.state != "resolved"
            for batch in batches for capture in batch.captures.all())
        review = finalisation_status(session)
        records = {str(row.student_id): row.status for row in session.records.all()}
        excusals = list(session.excusals.all())
        excused_ids = {str(row.student_id) for row in excusals if row.is_excused}
        for excusal in excusals:
            sid = str(excusal.student_id)
            if excusal.is_excused and excusal.retrospective and sid not in session.student_ids:
                totals.setdefault(sid, empty_rate_row(sid))["retrospective_excused_meetings"] += 1
        for sid in session.student_ids:
            row = totals.setdefault(sid, empty_rate_row(sid))
            row["finalised_meetings"] += review["finalised"]
            row["stale_finalisation_meetings"] += review["review_stale"]
            pending = (unresolved or finalised_only) and not review["finalised"]
            row["pending_meetings"] += pending
            if sid in excused_ids:
                row["excused_meetings"] += 1
                continue
            if pending:
                continue
            row["eligible_recorded_meetings"] += 1
            row["meetings_attended"] += records.get(sid) == "present"
    for row in totals.values():
        denominator = row["eligible_recorded_meetings"]
        row["rate_percent"] = str((Decimal(row["meetings_attended"]) * 100 / denominator).quantize(Decimal("0.01"))) if denominator else None
    return sorted((row for row in totals.values() if student is None or row["student_id"] == str(student.pk)), key=lambda row: row["student_id"])
