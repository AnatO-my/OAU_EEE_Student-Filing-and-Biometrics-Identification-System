"""Synthetic capture evidence only: no scanner, private files or shared database."""
import base64
import copy
import hashlib
import importlib
import io
import json
from pathlib import Path
import struct
import sys
import uuid
from datetime import timedelta
from unittest.mock import patch
import zlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from academics.current_session import select_current_session
from academics.models import AcademicSession, Course, CourseOffering, CurrentAcademicSession, GradingScale
from students.models import Student
from .models import (AttendanceCorrection, AttendanceEvent, AttendanceRecord,
                     PendingBatchImport, PendingCaptureBatch, PendingCaptureEvent)
from .pending_format import (BatchFormatError, MAX_EVENTS, MAX_FILE_BYTES, MAX_LINE_BYTES,
                             PROBE_FORMAT, parse_capture_file, read_batch_stream)
from .pending_services import PendingBatchConflict, import_pending_batch, preview_pending_batch
from .services import assign_staff, close_session, confirm_roster, open_session, record_manual


# Build synthetic but structurally valid metadata tied to the requested meeting.
def header(session_id=None):
    return {"kind": "capture_batch", "schema_version": 1, "device_uuid": str(uuid.uuid4()),
            "batch_uuid": str(uuid.uuid4()), "class_session_uuid": str(session_id or uuid.uuid4()),
            "scanner_uuid": str(uuid.uuid4()), "compatibility_group": "as608-synthetic",
            "probe_format": PROBE_FORMAT, "interrupted_write_pending": False,
            "source": {"capacity": 150, "security_level": 3, "packet_bytes": 128,
                       "system_id": 0, "device_address": "FFFFFFFF"},
            "clock": {"basis": "boot_elapsed", "wall_clock_verified": False, "timezone": None}}


# Create one opaque synthetic capture without using real biometric material.
def event(*, event_id=None, boot_id=None, uptime=10, probe=b"synthetic-probe-only"):
    return {"kind": "capture", "event_uuid": str(event_id or uuid.uuid4()),
            "boot_uuid": str(boot_id or uuid.uuid4()), "uptime_ms": uptime, "captured_at": None,
            "probe_base64": base64.b64encode(probe).decode("ascii")}


# Serialize JSONL records and seal the body with its count and SHA-256 digest.
def pack(metadata, events, *, trailer_update=None):
    body = b"".join((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    for value in [metadata, *events])
    trailer = {"kind": "end", "record_count": len(events), "sha256": hashlib.sha256(body).hexdigest()}
    trailer.update(trailer_update or {})
    return body + (json.dumps(trailer) + "\n").encode()


# Exercise parser acceptance, bounds, canonicalization, and sanitized failures.
class CaptureFormatTests(SimpleTestCase):
    # Preserve maximum unsigned uptime while keeping identity and wall time unknown.
    def test_empty_and_full_uint64_captures_keep_unknown_time_and_identity(self):
        for events in ([], [event(uptime=2**64-1, probe=b"x" * 2048)]):
            result = parse_capture_file(pack(header(), events))
            self.assertEqual(len(result.events), len(events))
            if events:
                self.assertEqual(result.events[0].uptime_ms, 2**64-1)
                self.assertNotIn("probe_base64", repr(result))

    # Keep the documented USB downloader's output compatible with the parser.
    def test_accepts_current_usb_downloader_output(self):
        tools = Path(__file__).resolve().parents[2] / "hardware" / "fingerprint-diagnostic" / "tools"
        with patch.object(sys, "path", [str(tools), *sys.path]):
            downloader = importlib.import_module("deferred_batches")
        seal = lambda value: value + struct.pack(">I", zlib.crc32(value))
        raw_header = seal(b"FPB1" + b"".join(uuid.uuid4().bytes for _ in range(4))
                          + b"as608-synthetic".ljust(80, b"\0") + struct.pack(">HHHHI", 150, 3, 128, 0, 0xFFFFFFFF))
        metadata = downloader.decode_header(raw_header)
        metadata["interrupted_write_pending"] = False
        raw_event = seal(b"FPE1" + uuid.uuid4().bytes + uuid.uuid4().bytes
                         + struct.pack(">QH", 500, 9) + b"synthetic")
        body = downloader.json_line(metadata) + downloader.json_line(downloader.decode_event(raw_event))
        data = body + downloader.json_line({"kind": "end", "record_count": 1,
                                           "sha256": hashlib.sha256(body).hexdigest()})
        self.assertEqual(parse_capture_file(data).events[0].probe, b"synthetic")

    # Stop oversized streams after the configured limit plus one sentinel byte.
    def test_stream_read_is_bounded_even_without_content_length(self):
        stream = io.BytesIO(b"x" * (MAX_FILE_BYTES + 10000))
        with self.assertRaises(BatchFormatError):
            read_batch_stream(stream)
        self.assertEqual(stream.tell(), MAX_FILE_BYTES + 1)
        self.assertEqual(read_batch_stream(io.BytesIO(b"abc")), b"abc")
        with self.assertRaises(BatchFormatError):
            read_batch_stream(None)

    # Reject incomplete files, altered records, and invalid trailer integrity data.
    def test_truncation_corruption_and_count_digest_mismatches(self):
        original = pack(header(), [event()])
        variants = [original[:-1], original[:-25], original.replace(b"synthetic", b"corrupted", 1),
                    pack(header(), [], trailer_update={"record_count": 1}),
                    pack(header(), [], trailer_update={"record_count": False}),
                    pack(header(), [], trailer_update={"sha256": "0" * 64})]
        for data in variants:
            with self.subTest(size=len(data)), self.assertRaises(BatchFormatError):
                parse_capture_file(data)

    # Enforce maximum file, line, and event counts while accepting exact limits.
    def test_file_line_and_event_bounds(self):
        for data in (b"x" * (MAX_FILE_BYTES + 1) + b"\n", b" " * (MAX_LINE_BYTES+1) + b"\n{}\n",
                     pack(header(), [event() for _ in range(MAX_EVENTS + 1)])):
            with self.assertRaises(BatchFormatError):
                parse_capture_file(data)
        self.assertEqual(len(parse_capture_file(pack(header(), [event() for _ in range(MAX_EVENTS)])).events), MAX_EVENTS)

    # Hide attacker-controlled input from errors for malformed JSON and encoding.
    def test_duplicate_fields_nonfinite_numbers_and_invalid_utf8_are_sanitized(self):
        for data in (b'{"private-marker":1,"private-marker":2}\n{}\n', b'{"secret":NaN}\n{}\n',
                     b'\xffprivate-marker\n{}\n', b'[[[["private-marker"\n{}\n', b'['*1100+b'\n{}\n'):
            with self.assertRaises(BatchFormatError) as caught:
                parse_capture_file(data)
            self.assertNotIn("private-marker", str(caught.exception))

    # Require exact schemas at every record level, with no missing or extra keys.
    def test_missing_and_unknown_fields_are_rejected_at_every_level(self):
        for where in ("header", "source", "clock", "event", "trailer"):
            for remove in (False, True):
                metadata, capture, tail = header(), event(), {}
                target = {"header": metadata, "source": metadata["source"], "clock": metadata["clock"],
                          "event": capture, "trailer": tail}[where]
                if remove:
                    if where == "trailer":
                        tail["kind"] = None
                    else:
                        target.pop(next(iter(target)))
                else:
                    target["student_id"] = str(uuid.uuid4())
                with self.subTest(where=where, remove=remove), self.assertRaises(BatchFormatError):
                    parse_capture_file(pack(metadata, [capture], trailer_update=tail))

    # Reject unsupported scanner metadata and any unverified wall-clock claims.
    def test_invalid_source_and_clock_metadata(self):
        for path, value in (("schema_version", True), ("schema_version", 2), ("probe_format", "template"),
                            ("compatibility_group", "x"*80), ("interrupted_write_pending", 1),
                            ("source.capacity", True), ("source.capacity", 0), ("source.packet_bytes", 128.0),
                            ("source.system_id", -1), ("source.device_address", "ffffffff"),
                            ("clock.wall_clock_verified", 0), ("clock.wall_clock_verified", True),
                            ("clock.timezone", "Africa/Lagos")):
            metadata = header()
            keys = path.split(".")
            target = metadata if len(keys) == 1 else metadata[keys[0]]
            target[keys[-1]] = value
            with self.subTest(path=path), self.assertRaises(BatchFormatError):
                parse_capture_file(pack(metadata, []))

    # Accept only canonical nonzero string UUIDs throughout batch metadata.
    def test_uuid_aliases_nil_and_nonstrings_rejected(self):
        for key in ("batch_uuid", "device_uuid", "scanner_uuid", "class_session_uuid"):
            for value in (str(uuid.UUID(int=0)), "A"*32, None, str(uuid.uuid4()).upper()):
                metadata = header()
                metadata[key] = value
                with self.subTest(key=key), self.assertRaises(BatchFormatError):
                    parse_capture_file(pack(metadata, []))

    # Validate event time, identity, and canonical bounded Base64 probe data.
    def test_probe_and_event_validation(self):
        for update in ({"uptime_ms": True}, {"uptime_ms": -1}, {"uptime_ms": 2**64}, {"uptime_ms": 1.0},
                       {"captured_at": "2026-10-16T12:00:00Z"}, {"event_uuid": str(uuid.UUID(int=0))},
                       {"boot_uuid": []}, {"probe_base64": ""}, {"probe_base64": "%%%"},
                       {"probe_base64": "eB=="}, {"probe_base64": base64.b64encode(b"x"*2049).decode()}):
            capture = {**event(), **update}
            with self.subTest(keys=list(update)), self.assertRaises(BatchFormatError):
                parse_capture_file(pack(header(), [capture]))

    # Enforce unique event IDs and nondecreasing elapsed time within each boot.
    def test_duplicate_ids_and_elapsed_order_per_boot(self):
        first = event(uptime=100)
        for second in (first, event(boot_id=first["boot_uuid"], uptime=99)):
            with self.assertRaises(BatchFormatError):
                parse_capture_file(pack(header(), [first, second]))
        self.assertEqual(len(parse_capture_file(pack(header(), [first, event(uptime=0)])).events), 2)


# Share synthetic course setup and direct/API helpers across persistence tests.
class PendingBatchFixtureMixin:
    # Create isolated staff, student, offering, roster, and open-session fixtures.
    def setUp(self):
        super().setUp()
        # Transaction/live-server tests flush data migrations between test methods.
        CurrentAcademicSession.objects.get_or_create(pk=1)
        User = get_user_model()
        self.hod = User.objects.create_superuser(username="pending-hod", email="hod@example.invalid", password="synthetic")
        self.staff = User.objects.create_user(username="pending-staff", is_staff=True)
        self.other = User.objects.create_user(username="pending-unassigned", is_staff=True)
        self.student_user = User.objects.create_user(username="pending-student")
        for staff in (self.staff, self.other):
            staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="attendance"))
        self.year = AcademicSession.objects.create(name="2026/2027")
        course = Course.objects.create(code="EEE202", title="Synthetic capture course")
        scale, _ = GradingScale.objects.get_or_create(name="Synthetic pending scale", defaults={
            "bands": [{"minimum": "0", "maximum": "100", "grade_point": "5"}], "is_published": True})
        self.offering = CourseOffering.objects.create(course=course, academic_session=self.year,
            semester="harmattan", level=200, credit_units=3, grading_scale=scale)
        self.student = Student.objects.create(identifier_type="matriculation", identifier_value="PEND-001",
            full_name="Synthetic Student", phone_number="+2340000000000", admission_year=2024,
            mode_of_admission="utme", current_level=200, user=self.student_user)
        assign_staff(user=self.hod, offering=self.offering, staff=self.staff, is_active=True)
        confirm_roster(user=self.hod, offering=self.offering, student_ids=[self.student.pk], expected_revision=0)
        self.session = self.new_session()
        self.metadata, self.events = header(self.session.pk), [event()]
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.url = f"/api/attendance/sessions/{self.session.pk}/pending-batches/"

    # Create another authorized meeting for binding and visibility assertions.
    def new_session(self):
        now = timezone.now()
        return open_session(user=self.staff, offering=self.offering, title="Synthetic class",
            starts_at=now-timedelta(hours=2), ends_at=now-timedelta(hours=1))

    # Return the current fixture as a complete, checksummed interchange file.
    def data(self):
        return pack(self.metadata, self.events)

    # Call the service with fixture defaults and optional identity overrides.
    def preview(self, **kwargs):
        return preview_pending_batch(user=kwargs.get("user", self.staff), session=kwargs.get("session", self.session), data=self.data())

    # Import the current file using its digest unless a test supplies another.
    def ingest(self, **kwargs):
        data = self.data()
        return import_pending_batch(user=kwargs.get("user", self.staff), session=kwargs.get("session", self.session),
            data=data, expected_sha256=kwargs.get("digest", hashlib.sha256(data).hexdigest()))

    # Submit a raw NDJSON body through the API with an optional preview digest.
    def upload(self, path=None, *, digest=True, data=None):
        data = self.data() if data is None else data
        extra = {"HTTP_X_CAPTURE_SHA256": hashlib.sha256(data).hexdigest()} if digest else {}
        return self.client.post(path or self.url, data, content_type="application/x-ndjson", **extra)


# Verify authorized imports remain pending evidence and preserve immutable retries.
@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class PendingBatchTests(PendingBatchFixtureMixin, TestCase):
    # Ensure preview reports review requirements but creates no durable records.
    def test_preview_writes_nothing_and_reports_pending_reviews(self):
        before = (PendingCaptureBatch.objects.count(), PendingCaptureEvent.objects.count(), PendingBatchImport.objects.count())
        result = self.preview()
        self.assertEqual((result["new_events"], result["existing_events"]), (1, 0))
        self.assertFalse(result["device_authenticated"])
        self.assertTrue(result["identity_review_required"] and result["timing_review_required"])
        self.assertEqual(before, (PendingCaptureBatch.objects.count(), PendingCaptureEvent.objects.count(), PendingBatchImport.objects.count()))

    # Persist probes and a receipt without creating or changing attendance records.
    def test_import_persists_evidence_receipt_and_never_attendance(self):
        result = self.ingest()
        capture = PendingCaptureEvent.objects.get()
        self.assertIsNone(capture.captured_at)
        self.assertEqual(bytes(capture.probe), b"synthetic-probe-only")
        self.assertTrue(result["device_files_must_be_retained"])
        self.assertFalse(result["replayed"])
        self.assertEqual(str(PendingBatchImport.objects.get().pk), result["receipt_id"])
        for model in (AttendanceRecord, AttendanceEvent, AttendanceCorrection):
            self.assertEqual(model.objects.count(), 0)

    # Store unsigned 64-bit elapsed time exactly, including on retry.
    def test_uint64_uptime_roundtrips_exactly(self):
        self.events[0]["uptime_ms"] = 2**64-1
        first = self.ingest()
        self.assertEqual(int(PendingCaptureEvent.objects.get().uptime_ms), 2**64-1)
        self.assertEqual(self.ingest()["receipt_id"], first["receipt_id"])

    # Reuse the original receipt and importer when the same snapshot is retried.
    def test_exact_retry_retains_receipt_and_first_importer(self):
        first = self.ingest()
        retry = self.ingest(user=self.hod)
        self.assertTrue(retry["replayed"])
        self.assertEqual(retry["receipt_id"], first["receipt_id"])
        self.assertEqual((retry["new_events"], retry["existing_events"]), (0, 1))
        self.assertEqual(PendingCaptureBatch.objects.get().imported_by, self.staff)
        self.assertEqual(PendingBatchImport.objects.get().imported_by, self.staff)
        self.assertEqual(PendingCaptureEvent.objects.count(), 1)

    # Append new events while retaining idempotent access to an older snapshot.
    def test_append_import_and_old_snapshot_retry(self):
        old = copy.deepcopy(self.events)
        first = self.ingest()
        self.events.append(event(boot_id=old[0]["boot_uuid"], uptime=20))
        preview = self.preview()
        self.assertEqual((preview["new_events"], preview["existing_events"]), (1, 1))
        second = self.ingest()
        self.assertNotEqual(first["receipt_id"], second["receipt_id"])
        self.events = old
        retry = self.ingest()
        self.assertEqual((retry["receipt_id"], retry["batch_event_count"]), (first["receipt_id"], 2))
        self.assertEqual(PendingCaptureEvent.objects.count(), 2)

    # Reject edits or reordering within an accepted prefix without partial writes.
    def test_changed_event_or_reordered_snapshot_rejected_atomically(self):
        self.events.append(event())
        self.ingest()
        original = copy.deepcopy(self.events)
        variants = [list(reversed(original))]
        for key, value in (("probe_base64", base64.b64encode(b"different-synthetic").decode()),
                           ("boot_uuid", str(uuid.uuid4())), ("uptime_ms", 50),
                           ("event_uuid", str(uuid.uuid4()))):
            changed = copy.deepcopy(original)
            changed[0][key] = value
            variants.append(changed)
        for changed in variants:
            self.events = [*changed, event()]
            with self.assertRaises(PendingBatchConflict):
                self.ingest()
            self.assertEqual(PendingCaptureEvent.objects.count(), 2)
            self.assertEqual(PendingBatchImport.objects.count(), 1)

    # Prevent a batch UUID from changing metadata or moving to another meeting.
    def test_batch_metadata_and_session_binding_are_immutable(self):
        self.ingest()
        original = copy.deepcopy(self.metadata)
        for key, value in (("device_uuid", str(uuid.uuid4())), ("scanner_uuid", str(uuid.uuid4())),
                           ("compatibility_group", "other-scanner")):
            self.metadata = {**original, key: value}
            with self.assertRaises(PendingBatchConflict):
                self.ingest()
        other_session = self.new_session()
        self.metadata = {**original, "class_session_uuid": str(other_session.pk)}
        with self.assertRaises(PendingBatchConflict):
            self.ingest(session=other_session)

    # Reject synthetic/foreign meeting IDs and hide nonexistent meeting URLs.
    def test_wrong_or_synthetic_class_header_rejected(self):
        self.metadata["class_session_uuid"] = str(uuid.uuid4())
        with self.assertRaises(ValidationError):
            self.ingest()
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)
        unknown = self.client.post(f"/api/attendance/sessions/{uuid.uuid4()}/pending-batches/preview/",
            self.data(), content_type="application/x-ndjson")
        self.assertEqual(unknown.status_code, 404)

    # Keep capture event UUIDs unique across independently named batches.
    def test_event_uuid_cannot_cross_batches(self):
        self.ingest()
        self.metadata["batch_uuid"] = str(uuid.uuid4())
        with self.assertRaises(PendingBatchConflict):
            self.ingest()
        self.assertEqual(PendingCaptureBatch.objects.count(), 1)

    # Prevent UUID collisions between manually recorded and imported evidence.
    def test_manual_and_capture_event_uuid_collision_both_directions(self):
        self.ingest()
        with self.assertRaises(ValidationError):
            record_manual(user=self.staff, session=self.session, student=self.student,
                event_id=uuid.UUID(self.events[0]["event_uuid"]), reason="Manual synthetic")
        self.session.starts_at = timezone.now()-timedelta(minutes=1)
        self.session.ends_at = timezone.now()+timedelta(minutes=1)
        self.session.save()
        manual_id = uuid.uuid4()
        record_manual(user=self.staff, session=self.session, student=self.student,
            event_id=manual_id, reason="Manual synthetic")
        self.metadata["batch_uuid"] = str(uuid.uuid4())
        self.events = [event(event_id=manual_id)]
        with self.assertRaises(PendingBatchConflict):
            self.ingest()

    # Require the preview digest and reject changed content before writing.
    def test_preview_digest_required_and_changed_file_rejected(self):
        digest = self.preview()["file_sha256"]
        for invalid in (None, "", "not-a-digest", "0"*64):
            with self.assertRaises(ValidationError):
                self.ingest(digest=invalid)
        self.events.append(event())
        with self.assertRaises(PendingBatchConflict):
            self.ingest(digest=digest)
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)

    # Keep recovery review required after any snapshot reports an interrupted write.
    def test_interrupted_write_review_is_sticky_across_snapshots(self):
        self.metadata["interrupted_write_pending"] = True
        self.ingest()
        self.metadata["interrupted_write_pending"] = False
        self.assertTrue(self.preview()["recovery_review_required"])
        self.ingest()
        self.assertTrue(PendingCaptureBatch.objects.get().recovery_review_required)
        self.assertEqual(set(PendingBatchImport.objects.values_list("interrupted_write_pending", flat=True)), {False, True})

    # Allow empty or late evidence to remain pending without recording attendance.
    def test_empty_batch_and_closed_late_import_stay_pending(self):
        self.events = []
        close_session(user=self.staff, session=self.session)
        result = self.ingest()
        self.assertEqual((result["state"], result["event_count"]), ("pending_review", 0))
        self.events = [event()]
        self.assertTrue(self.ingest()["timing_review_required"])
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    # Roll back the batch and events if durable receipt creation fails.
    def test_failure_during_commit_rolls_back_batch_events_and_receipt(self):
        with patch.object(PendingBatchImport.objects, "get_or_create", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.ingest()
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)
        self.assertEqual(PendingCaptureEvent.objects.count(), 0)

    # Enforce course assignment at the service boundary for all callers.
    def test_unassigned_staff_and_students_denied_at_service_boundary(self):
        for user in (self.other, self.student_user):
            for action in (self.preview, self.ingest):
                with self.assertRaises(PermissionDenied):
                    action(user=user)

    # Require the dedicated permission even for staff assigned to the offering.
    def test_assignment_without_restricted_permission_denied(self):
        self.staff.user_permissions.remove(Permission.objects.get(codename="import_pending_captures"))
        # A new request reloads its user instead of retaining Django's per-user permission cache.
        self.staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(self.staff)
        with self.assertRaises(PermissionDenied):
            self.preview()
        self.assertEqual(self.upload().status_code, 403)

    # Revoke preview, retry, and list access when a course assignment is disabled.
    def test_revoked_staff_cannot_preview_import_or_retry(self):
        self.ingest()
        assign_staff(user=self.hod, offering=self.offering, staff=self.staff, is_active=False)
        for action in (self.preview, self.ingest):
            with self.assertRaises(PermissionDenied):
                action()
        self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    # Deny evidence access to inactive users and accounts that are not staff.
    def test_inactive_or_nonstaff_importer_denied(self):
        for attribute in ("is_active", "is_staff"):
            setattr(self.staff, attribute, False)
            self.staff.save()
            with self.assertRaises(PermissionDenied):
                self.ingest()
            self.assertEqual(self.upload().status_code, 403)
            setattr(self.staff, attribute, True)

    # Verify academic-session cutover revokes ordinary staff import access.
    def test_current_session_cutover_revokes_ordinary_import_access(self):
        self.ingest()
        year = AcademicSession.objects.create(name="2027/2028")
        select_current_session(user=self.hod, academic_session=year, expected_session_id=None)
        with self.assertRaises(PermissionDenied):
            self.ingest()
        self.assertTrue(self.ingest(user=self.hod)["replayed"])

    # Check API preview/import/retry/list responses never return biometric probes.
    def test_api_preview_import_retry_list_and_no_biometric_response(self):
        preview = self.upload(self.url + "preview/")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)
        first, retry = self.upload(), self.upload()
        self.assertEqual((first.status_code, retry.status_code), (201, 200))
        self.assertEqual(first.data["receipt_id"], retry.data["receipt_id"])
        rows = self.client.get(self.url)
        self.assertEqual((rows.status_code, rows.data["count"]), (200, 1))
        for response in (preview, first, retry, rows):
            self.assertNotIn("probe_base64", response.content.decode())
            self.assertNotIn(self.events[0]["probe_base64"], response.content.decode())
            self.assertIn("no-store", response["Cache-Control"])

    # Map conflicts, missing digest, size limits, and unsupported media correctly.
    def test_api_conflicts_validation_size_media_and_empty_body(self):
        self.assertEqual(self.upload(digest=False).status_code, 400)
        self.ingest()
        self.events[0]["uptime_ms"] = 12
        self.assertEqual(self.upload().status_code, 409)
        self.assertEqual(self.upload(self.url + "preview/").status_code, 409)
        self.assertEqual(self.upload(data=b"x"*(MAX_FILE_BYTES+1)).status_code, 400)
        self.assertEqual(self.upload(data=b"").status_code, 400)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 415)

    # Reject a commit whose uploaded bytes no longer match the preview digest.
    def test_api_rejects_file_changed_after_preview(self):
        preview = self.upload(self.url + "preview/")
        self.events.append(event())
        response = self.client.post(self.url, self.data(), content_type="application/x-ndjson",
                                   HTTP_X_CAPTURE_SHA256=preview.data["file_sha256"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)

    # Hide foreign-course evidence before parsing potentially sensitive request data.
    def test_api_hides_other_course_evidence_before_parsing(self):
        self.ingest()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        with patch("attendance.pending_views.read_batch_stream") as read:
            self.assertEqual(self.upload(self.url + "preview/", data=b"bad-private-input").status_code, 404)
            read.assert_not_called()

    # Require authenticated staff and CSRF protection without exposing student data.
    def test_api_auth_csrf_and_student_privacy(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.upload().status_code, 403)
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.upload().status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(self.url, self.data(), content_type="application/x-ndjson",
                               HTTP_X_CAPTURE_SHA256=hashlib.sha256(self.data()).hexdigest())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)

    # Keep biometric evidence models unavailable through the Django admin.
    def test_probe_models_are_not_exposed_through_admin(self):
        from django.contrib import admin
        for model in (PendingCaptureBatch, PendingCaptureEvent, PendingBatchImport):
            self.assertNotIn(model, admin.site._registry)
