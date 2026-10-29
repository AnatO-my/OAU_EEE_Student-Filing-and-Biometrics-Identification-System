"""Explicit reviewed closure policy bound to the evidence actually available."""
import hashlib
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import AttendanceSession, MeetingFinalisation
from .services import lock_calendar, require_course
from .excusals import excusal_snapshot


def evidence_digest(session):
    """Exclude mutable identity decisions so later audited resolution stays useful."""
    batches = []
    for batch in session.pending_capture_batches.order_by("pk"):
        batches.append({"id": str(batch.pk), "metadata": batch.metadata,
            "recovery_review_required": batch.recovery_review_required,
            "captures": [{"id": str(row.pk), "ordinal": row.ordinal,
                "boot_uuid": str(row.boot_uuid), "uptime_ms": row.uptime_ms,
                "probe_sha256": hashlib.sha256(bytes(row.probe)).hexdigest()}
                for row in batch.captures.order_by("ordinal")],
            "imports": list(batch.imports.order_by("file_sha256").values_list("file_sha256", flat=True))})
    payload = {"meeting_id": str(session.pk), "offering_id": session.offering_id,
               "roster_revision": session.roster_revision, "student_ids": sorted(session.student_ids),
               "starts_at": session.starts_at.isoformat(), "ends_at": session.ends_at.isoformat(),
               "batches": batches}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def review_snapshot(session, digest):
    records = [{"record_id": row.pk, "student_id": str(row.student_id), "status": row.status}
               for row in session.records.order_by("student_id")]
    excusals = excusal_snapshot(session)
    payload = {"evidence_sha256": digest, "confirmed_records": records, "confirmed_excusals": excusals}
    review_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return records, excusals, review_digest


def finalisation_status(session):
    digest = evidence_digest(session)
    latest = session.finalisations.order_by("-revision").first()
    records, excusals, review_digest = review_snapshot(session, digest)
    return {"meeting_id": str(session.pk), "evidence_sha256": digest,
            "review_sha256": review_digest, "confirmed_records": records, "confirmed_excusals": excusals,
            "last_reviewed_records": latest.records_snapshot if latest else [],
            "last_reviewed_excusals": latest.excusals_snapshot if latest else [],
            "collection_status": session.status,
            "finalised": bool(latest and session.status == "closed" and latest.evidence_sha256 == digest),
            "review_stale": bool(latest and latest.evidence_sha256 != digest),
            "revision": latest.revision if latest else 0,
            "reviewed_by": latest.reviewed_by_id if latest else None,
            "reviewed_at": latest.reviewed_at if latest else None,
            "reason": latest.reason if latest else None,
            "archived_captures_are_retained": True}


@transaction.atomic
def inspect_finalisation(*, user, session):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "correct_attendance")
    return finalisation_status(session)


@transaction.atomic
def finalise_meeting(*, user, session, expected_digest, reviewed, reason):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "correct_attendance")
    reason = reason.strip()
    if session.status != "closed":
        raise ValidationError("Close attendance collection before explicitly finalising this meeting.")
    if reviewed is not True or not reason:
        raise ValidationError("Confirm that the meeting attendance and remaining archived captures were reviewed, with a reason.")
    digest = evidence_digest(session)
    records, excusals, review_digest = review_snapshot(session, digest)
    latest = session.finalisations.order_by("-revision").first()
    if latest and latest.evidence_sha256 == digest and (
            latest.review_sha256, latest.reviewed_by_id, latest.reason) == (expected_digest, user.pk, reason):
        return {**finalisation_status(session), "replayed": True}
    if expected_digest != review_digest:
        raise ValidationError("The meeting evidence or confirmed records changed. Review them again before finalising.")
    MeetingFinalisation.objects.create(session=session, revision=latest.revision + 1 if latest else 1,
        evidence_sha256=digest, review_sha256=review_digest, records_snapshot=records, excusals_snapshot=excusals,
        student_ids=sorted(session.student_ids), reviewed_by=user, reason=reason)
    return {**finalisation_status(session), "replayed": False}
