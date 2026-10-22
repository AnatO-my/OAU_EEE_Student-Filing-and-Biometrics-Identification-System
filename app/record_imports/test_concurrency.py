"""Observe real PostgreSQL lock contention, including retries and rollback."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from academics.models import Result
from academics.services import create_result
from students.models import Student
from students.services import update_student
from .models import ImportBatch, ImportChange
from .services import ImportConflict, commit_import
from .test_imports import ImportFixture


class SyntheticRollback(Exception):
    pass


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL row locks.")
@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class ImportConcurrencyTests(ImportFixture, TransactionTestCase):
    def fresh_hod(self):
        return get_user_model().objects.get(pk=self.hod.pk)

    def import_batch(self, batch):
        return commit_import(user=self.fresh_hod(), batch_id=batch.pk,
            preview_digest=batch.preview_digest, correction_approvals=[])

    def contend(self, first, second, rollback=False, after_hold=None):
        ready, release, connected = Event(), Event(), Event()
        pids = {}
        def run(action, hold):
            conn = connections["default"]
            conn.close()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids["first" if hold else "second"] = cursor.fetchone()[0]
                if not hold:
                    connected.set()
                with transaction.atomic():
                    result = action()
                    if hold:
                        ready.set()
                        if not release.wait(10):
                            raise AssertionError("Coordinator did not release the held transaction.")
                        if after_hold:
                            after_hold()
                        if rollback:
                            raise SyntheticRollback()
                    return result
            except (ValidationError, PermissionDenied, SyntheticRollback) as error:
                return error
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            left = executor.submit(run, first, True)
            right = None
            try:
                if not ready.wait(8):
                    self.fail(f"First transaction failed before contention: {left.result(timeout=1)!r}")
                right = executor.submit(run, second, False)
                self.assertTrue(connected.wait(5))
                deadline = time.monotonic() + 5
                blocked = False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [pids["first"], pids["second"]])
                        blocked = cursor.fetchone()[0]
                    if blocked:
                        break
                    if right.done():
                        self.fail(f"Second transaction did not contend: {right.result()!r}")
                    time.sleep(0.01)
                self.assertTrue(blocked, "PostgreSQL did not observe actual row-lock contention.")
            finally:
                release.set()
            return left.result(timeout=15), right.result(timeout=15)

    def test_identical_commit_retry_has_one_durable_receipt(self):
        batch = self.preview()
        first, second = self.contend(lambda: self.import_batch(batch), lambda: self.import_batch(batch))
        self.assertFalse(first[1])
        self.assertTrue(second[1])
        self.assertEqual(first[0].receipt, second[0].receipt)
        self.assertEqual(Result.objects.count(), 1)
        self.assertEqual(ImportChange.objects.count(), 1)

    def test_overlapping_previews_cannot_create_duplicate_results(self):
        first, second = self.preview(), self.preview()
        left, right = self.contend(lambda: self.import_batch(first), lambda: self.import_batch(second))
        self.assertFalse(left[1])
        self.assertIsInstance(right, ImportConflict)
        self.assertEqual(Result.objects.count(), 1)
        second.refresh_from_db()
        self.assertEqual(second.status, "preview")

    def test_overlapping_rosters_cannot_duplicate_students(self):
        row = self.roster_row()
        first, second = self.preview("roster", [row]), self.preview("roster", [row])
        left, right = self.contend(lambda: self.import_batch(first), lambda: self.import_batch(second))
        self.assertFalse(left[1])
        self.assertIsInstance(right, ImportConflict)
        self.assertEqual(Student.objects.filter(identifier_value=row["identifier_value"]).count(), 1)

    def test_failed_transaction_rolls_back_records_audit_and_receipt_then_retry_succeeds(self):
        batch = self.preview()
        first, second = self.contend(lambda: self.import_batch(batch), lambda: self.import_batch(batch), rollback=True)
        self.assertIsInstance(first, SyntheticRollback)
        self.assertFalse(second[1])
        self.assertEqual(Result.objects.count(), 1)
        self.assertEqual(ImportChange.objects.count(), 1)
        batch.refresh_from_db()
        self.assertEqual(batch.status, "committed")

    def test_manual_result_create_blocks_import_then_invalidates_preview(self):
        batch = self.preview()
        def manual():
            return create_result(user=self.fresh_hod(), student=self.student, offering=self.offering)
        left, right = self.contend(manual, lambda: self.import_batch(batch))
        self.assertIsInstance(left, Result)
        self.assertIsInstance(right, ImportConflict)
        self.assertEqual(Result.objects.count(), 1)
        self.assertEqual(ImportChange.objects.count(), 0)

    def test_manual_student_edit_and_import_use_compatible_lock_order(self):
        batch = self.preview(user=self.staff)
        def manual_lock():
            return Student.objects.select_for_update().get(pk=self.student.pk)
        def manual_edit():
            return update_student(user=get_user_model().objects.get(pk=self.staff.pk), student=self.student,
                validated_data={"full_name": "Reviewed Existing Student"})
        def ingest():
            return commit_import(user=get_user_model().objects.get(pk=self.staff.pk), batch_id=batch.pk,
                preview_digest=batch.preview_digest, correction_approvals=[])
        left, right = self.contend(manual_lock, ingest, after_hold=manual_edit)
        self.assertIsInstance(left, Student)
        self.assertIsInstance(right, ImportConflict)
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Reviewed Existing Student")
        self.assertEqual(Result.objects.count(), 0)
