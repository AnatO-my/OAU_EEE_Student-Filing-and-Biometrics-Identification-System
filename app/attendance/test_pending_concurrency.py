"""Real PostgreSQL row-lock contention using independent worker connections."""
import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from unittest import skipUnless
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from academics.current_session import select_current_session
from academics.models import AcademicSession
from .models import (AttendanceEvent, AttendanceRecord, CourseStaffAssignment,
                     PendingBatchImport, PendingCaptureBatch, PendingCaptureEvent)
from .pending_services import PendingBatchConflict, import_pending_batch
from .services import assign_staff, record_manual
from .test_pending_batches import PendingBatchFixtureMixin, event, pack


class SimulatedRollback(Exception):
    pass


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL row locks.")
@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class PendingBatchConcurrencyTests(PendingBatchFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        # Manual recording races need an open window; importer also accepts late evidence.
        self.session.starts_at = timezone.now() - timedelta(minutes=5)
        self.session.ends_at = timezone.now() + timedelta(minutes=5)
        self.session.save()

    def fresh_user(self, user=None):
        return get_user_model().objects.get(pk=(user or self.staff).pk)

    def ingest_data(self, data):
        return import_pending_batch(user=self.fresh_user(), session=self.session, data=data,
                                    expected_sha256=hashlib.sha256(data).hexdigest())

    def overlap(self, first, second, *, rollback_first=False):
        """Hold the first transaction open until PostgreSQL confirms the second waits.

        No production method is mocked. A coordinator connection observes the
        server's lock graph, so scheduler timing cannot turn this into a serial test.
        """
        staged, release, second_connected = Event(), Event(), Event()
        pids = {}

        def worker(action, *, hold):
            conn = connections["default"]
            conn.close()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids["first" if hold else "second"] = cursor.fetchone()[0]
                if not hold:
                    second_connected.set()
                with transaction.atomic():
                    result = action()
                    if hold:
                        staged.set()
                        if not release.wait(10):
                            raise AssertionError("Coordinator did not release the first transaction.")
                        if rollback_first:
                            raise SimulatedRollback("Synthetic failure before outer commit.")
                return result
            except (ValidationError, PermissionDenied, SimulatedRollback) as exc:
                return exc
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(worker, first, hold=True)
            right = None
            try:
                if not staged.wait(8):
                    self.fail(f"First transaction did not stage successfully: {left.result(timeout=1)!r}")
                right = pool.submit(worker, second, hold=False)
                self.assertTrue(second_connected.wait(5), "Second connection did not start.")
                deadline = time.monotonic() + 5
                blocked = False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [pids["first"], pids["second"]])
                        blocked = cursor.fetchone()[0]
                    if blocked:
                        break
                    if right.done():
                        self.fail(f"Second operation finished without contending: {right.result()!r}")
                    time.sleep(0.01)
                self.assertTrue(blocked, "PostgreSQL did not observe the expected row-lock contention.")
            finally:
                release.set()
            return left.result(timeout=12), right.result(timeout=12)

    def assert_evidence(self, *, events=1, receipts=1, batches=1):
        self.assertEqual(PendingCaptureBatch.objects.count(), batches)
        self.assertEqual(PendingCaptureEvent.objects.count(), events)
        self.assertEqual(PendingBatchImport.objects.count(), receipts)
        self.assertEqual(AttendanceRecord.objects.count(), 0)
        self.assertEqual(AttendanceEvent.objects.count(), 0)

    def test_concurrent_identical_import_returns_one_durable_receipt(self):
        data = self.data()
        first, retry = self.overlap(lambda: self.ingest_data(data), lambda: self.ingest_data(data))
        self.assertFalse(first["replayed"])
        self.assertTrue(retry["replayed"])
        self.assertEqual(first["receipt_id"], retry["receipt_id"])
        self.assert_evidence()

    def test_overlapping_snapshots_append_once(self):
        short = self.data()
        long = pack(self.metadata, [*self.events, event()])
        first, second = self.overlap(lambda: self.ingest_data(short), lambda: self.ingest_data(long))
        self.assertEqual((first["new_events"], second["new_events"]), (1, 1))
        self.assert_evidence(events=2, receipts=2)

    def test_short_snapshot_waiting_for_long_snapshot_creates_no_duplicate_events(self):
        short = self.data()
        long = pack(self.metadata, [*self.events, event()])
        first, second = self.overlap(lambda: self.ingest_data(long), lambda: self.ingest_data(short))
        self.assertEqual((first["new_events"], second["new_events"], second["batch_event_count"]), (2, 0, 2))
        self.assert_evidence(events=2, receipts=2)

    def test_append_racing_with_old_receipt_retry_preserves_both_snapshots(self):
        short = self.data()
        original = self.ingest_data(short)
        long = pack(self.metadata, [*self.events, event()])
        appended, retried = self.overlap(lambda: self.ingest_data(long), lambda: self.ingest_data(short))
        self.assertEqual(appended["new_events"], 1)
        self.assertEqual(retried["receipt_id"], original["receipt_id"])
        self.assertTrue(retried["replayed"])
        self.assert_evidence(events=2, receipts=2)

    def test_conflicting_concurrent_event_rolls_back_the_entire_losing_snapshot(self):
        data = self.data()
        changed = copy.deepcopy(self.events)
        changed[0]["uptime_ms"] += 1
        changed.append(event())
        conflict = pack(self.metadata, changed)
        _, loser = self.overlap(lambda: self.ingest_data(data), lambda: self.ingest_data(conflict))
        self.assertIsInstance(loser, PendingBatchConflict)
        self.assert_evidence()

    def test_event_uuid_racing_across_batches_leaves_no_orphan_batch(self):
        data = self.data()
        other = pack({**self.metadata, "batch_uuid": str(uuid.uuid4())}, self.events)
        _, loser = self.overlap(lambda: self.ingest_data(data), lambda: self.ingest_data(other))
        self.assertIsInstance(loser, PendingBatchConflict)
        self.assert_evidence()

    def manual(self):
        return record_manual(user=self.fresh_user(), session=self.session, student=self.student,
            event_id=uuid.UUID(self.events[0]["event_uuid"]), reason="Synthetic concurrent manual check")

    def test_capture_commit_prevents_colliding_manual_event(self):
        _, loser = self.overlap(lambda: self.ingest_data(self.data()), self.manual)
        self.assertIsInstance(loser, ValidationError)
        self.assert_evidence()

    def test_manual_commit_prevents_colliding_capture_event(self):
        _, loser = self.overlap(self.manual, lambda: self.ingest_data(self.data()))
        self.assertIsInstance(loser, PendingBatchConflict)
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)
        self.assertEqual(PendingCaptureEvent.objects.count(), 0)
        self.assertEqual(PendingBatchImport.objects.count(), 0)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceEvent.objects.count(), 1)

    def revoke(self):
        return assign_staff(user=self.fresh_user(self.hod), offering=self.offering,
                            staff=self.fresh_user(), is_active=False)

    def test_assignment_revocation_commits_before_waiting_import(self):
        _, denied = self.overlap(self.revoke, lambda: self.ingest_data(self.data()))
        self.assertIsInstance(denied, PermissionDenied)
        self.assert_evidence(events=0, receipts=0, batches=0)

    def test_import_commit_precedes_revocation_and_later_retry_is_denied(self):
        imported, _ = self.overlap(lambda: self.ingest_data(self.data()), self.revoke)
        self.assertFalse(imported["replayed"])
        self.assertFalse(CourseStaffAssignment.objects.get(staff=self.staff).is_active)
        with self.assertRaises(PermissionDenied):
            self.ingest_data(self.data())
        self.assert_evidence()

    def switch_calendar(self):
        return select_current_session(user=self.fresh_user(self.hod), academic_session=self.next_year,
                                      expected_session_id=None)

    def test_academic_session_cutover_commits_before_waiting_import(self):
        self.next_year = AcademicSession.objects.create(name="2027/2028")
        _, denied = self.overlap(self.switch_calendar, lambda: self.ingest_data(self.data()))
        self.assertIsInstance(denied, PermissionDenied)
        self.assert_evidence(events=0, receipts=0, batches=0)

    def test_import_commit_precedes_cutover_and_later_retry_is_denied(self):
        self.next_year = AcademicSession.objects.create(name="2027/2028")
        imported, _ = self.overlap(lambda: self.ingest_data(self.data()), self.switch_calendar)
        self.assertFalse(imported["replayed"])
        with self.assertRaises(PermissionDenied):
            self.ingest_data(self.data())
        self.assert_evidence()

    def test_waiting_retry_recovers_after_first_transaction_rolls_back(self):
        data = self.data()
        failed, recovered = self.overlap(lambda: self.ingest_data(data), lambda: self.ingest_data(data), rollback_first=True)
        self.assertIsInstance(failed, SimulatedRollback)
        self.assertFalse(recovered["replayed"])
        self.assert_evidence()

    def test_recovery_warning_survives_concurrent_clean_snapshot(self):
        damaged = pack({**self.metadata, "interrupted_write_pending": True}, self.events)
        clean = self.data()
        _, latest = self.overlap(lambda: self.ingest_data(damaged), lambda: self.ingest_data(clean))
        self.assertTrue(latest["recovery_review_required"])
        self.assertTrue(PendingCaptureBatch.objects.get().recovery_review_required)
        self.assert_evidence(receipts=2)
