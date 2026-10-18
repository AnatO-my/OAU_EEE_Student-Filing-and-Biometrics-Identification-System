"""Authorized pending evidence ingestion. This module never marks attendance."""
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (AttendanceEvent, AttendanceSession, PendingBatchImport,
                     PendingCaptureBatch, PendingCaptureEvent)
from .pending_format import BatchFormatError, SHA256_PATTERN, parse_capture_file
from .services import lock_calendar, require_course


# Distinguish immutable-evidence conflicts from invalid request data.
class PendingBatchConflict(ValidationError):
    pass


# Lock and authorize the target meeting before parsing or comparing evidence.
def _inspect(*, user, session, data):
    lock_calendar()
    session = AttendanceSession.objects.select_for_update().select_related("offering__academic_session").get(pk=session.pk)
    require_course(user, session.offering, "import_pending_captures")
    try:
        capture_file = parse_capture_file(data)
    except BatchFormatError as exc:
        raise ValidationError(str(exc)) from None
    metadata = capture_file.metadata
    if metadata["class_session_uuid"] != str(session.pk):
        raise ValidationError("The capture file belongs to a different class session.")
    batch = PendingCaptureBatch.objects.select_for_update().filter(pk=metadata["batch_uuid"]).first()
    if batch and (batch.session_id != session.pk or batch.metadata != metadata):
        raise PendingBatchConflict("The batch UUID is already bound to different metadata or a different class.")
    stored = list(batch.captures.order_by("ordinal")) if batch else []
    incoming_ids = [event.event_id for event in capture_file.events]
    if AttendanceEvent.objects.filter(pk__in=incoming_ids).exists():
        raise PendingBatchConflict("A capture event UUID is already used by an attendance event.")
    if PendingCaptureEvent.objects.filter(pk__in=incoming_ids).exclude(batch_id=metadata["batch_uuid"]).exists():
        raise PendingBatchConflict("A capture event UUID is already bound to another batch.")
    for ordinal, event in enumerate(capture_file.events[:len(stored)]):
        old = stored[ordinal]
        if (old.ordinal, old.pk, old.boot_uuid, int(old.uptime_ms), old.captured_at, bytes(old.probe)) != (
                ordinal, event.event_id, event.boot_id, event.uptime_ms, None, event.probe):
            raise PendingBatchConflict("An existing capture event or its position has changed.")
    # Snapshots are append-only. Old prefix downloads remain safe to retry.
    last_uptime = {}
    for old in stored:
        last_uptime[old.boot_uuid] = int(old.uptime_ms)
    for event in capture_file.events[len(stored):]:
        if event.uptime_ms < last_uptime.get(event.boot_id, -1):
            raise PendingBatchConflict("Appended captures move backwards within an existing boot.")
        last_uptime[event.boot_id] = event.uptime_ms
    return session, capture_file, batch, len(stored)


# Produce safe review state and append/replay counts without exposing probes.
def _summary(capture_file, batch, stored_count):
    count = len(capture_file.events)
    return {
        "batch_id": capture_file.metadata["batch_uuid"],
        "class_session_id": capture_file.metadata["class_session_uuid"],
        "file_sha256": capture_file.file_sha256,
        "metadata": capture_file.metadata,
        "event_count": count,
        "new_events": max(0, count - stored_count),
        "existing_events": min(count, stored_count),
        "batch_event_count": max(count, stored_count),
        "state": "pending_review",
        "identity_review_required": True,
        "timing_review_required": True,
        "device_authenticated": False,
        "interrupted_write_pending": capture_file.interrupted_write_pending,
        "recovery_review_required": capture_file.interrupted_write_pending or bool(batch and batch.recovery_review_required),
    }


# Preview under the same locks as import, but leave all evidence tables unchanged.
@transaction.atomic
def preview_pending_batch(*, user, session, data):
    _, capture_file, batch, stored_count = _inspect(user=user, session=session, data=data)
    return _summary(capture_file, batch, stored_count)


# Bind a previewed digest to an append-only batch and persist a durable receipt.
@transaction.atomic
def import_pending_batch(*, user, session, data, expected_sha256):
    session, capture_file, batch, stored_count = _inspect(user=user, session=session, data=data)
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValidationError("Supply the file SHA-256 returned by preview.")
    if capture_file.file_sha256 != expected_sha256:
        raise PendingBatchConflict("The capture file changed since preview. Preview the selected file again.")
    summary = _summary(capture_file, batch, stored_count)
    if batch is None:
        batch = PendingCaptureBatch.objects.create(pk=capture_file.metadata["batch_uuid"], session=session,
            metadata=capture_file.metadata, imported_by=user,
            recovery_review_required=capture_file.interrupted_write_pending)
    elif capture_file.interrupted_write_pending and not batch.recovery_review_required:
        batch.recovery_review_required = True
        batch.save(update_fields=["recovery_review_required"])
    PendingCaptureEvent.objects.bulk_create([
        PendingCaptureEvent(pk=event.event_id, batch=batch, ordinal=ordinal, boot_uuid=event.boot_id,
                            uptime_ms=str(event.uptime_ms), captured_at=None, probe=event.probe)
        for ordinal, event in enumerate(capture_file.events) if ordinal >= stored_count
    ])
    receipt, created = PendingBatchImport.objects.get_or_create(batch=batch, file_sha256=capture_file.file_sha256,
        defaults={"event_count": len(capture_file.events), "new_event_count": summary["new_events"],
                  "interrupted_write_pending": capture_file.interrupted_write_pending, "imported_by": user})
    return {**summary, "receipt_id": str(receipt.pk), "received_at": receipt.imported_at,
            "replayed": not created, "device_files_must_be_retained": True}
