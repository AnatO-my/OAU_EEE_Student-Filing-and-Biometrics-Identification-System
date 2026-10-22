"""Real PostgreSQL contention between different staff uploading one document type."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from accounts.models import AdviserAssignment
from students.models import Student

from .models import StudentDocument
from .services import process_upload
from .test_storage import isolate_document_storage
from .tests import make_pdf


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL row locks.")
@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027",
                   DOCUMENT_OCR_BACKEND="documents.tests.clear_scan_ocr")
class UploadConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.storage_root = isolate_document_storage(self)
        self.uploaders = []
        for index in (1, 2):
            staff = get_user_model().objects.create_user(username=f"synthetic-uploader-{index}", is_staff=True)
            staff.user_permissions.add(*Permission.objects.filter(
                content_type__app_label="students", codename="view_student"))
            staff.user_permissions.add(*Permission.objects.filter(
                content_type__app_label="documents", codename="add_studentdocument"))
            AdviserAssignment.objects.create(staff=staff, academic_session="2026/2027", level=300)
            self.uploaders.append(staff)
        self.student = Student.objects.create(identifier_type="matriculation", identifier_value="SYN-DOC-001",
            full_name="Synthetic Document Student", phone_number="+2340000000000", admission_year=2024,
            mode_of_admission="utme", current_level=300)

    def test_simultaneous_uploads_by_different_staff_leave_one_current_document(self):
        staged, release, second_connected = Event(), Event(), Event()
        pids = {}

        def upload(staff_id, *, hold):
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
                    document, decision = process_upload(
                        student=Student.objects.get(pk=self.student.pk), uploaded_file=make_pdf(),
                        document_type="result", uploaded_by=get_user_model().objects.get(pk=staff_id))
                    if not decision.accepted:
                        raise AssertionError("Synthetic clear document unexpectedly failed its quality gate.")
                    if hold:
                        staged.set()
                        if not release.wait(10):
                            raise AssertionError("Coordinator did not release the first upload.")
                return document.pk
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(upload, self.uploaders[0].pk, hold=True)
            second = None
            try:
                if not staged.wait(8):
                    self.fail(f"First upload did not stage: {first.result(timeout=1)!r}")
                second = pool.submit(upload, self.uploaders[1].pk, hold=False)
                self.assertTrue(second_connected.wait(5), "Second upload connection did not start.")
                deadline = time.monotonic() + 5
                blocked = False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [pids["first"], pids["second"]])
                        blocked = cursor.fetchone()[0]
                    if blocked:
                        break
                    if second.done():
                        self.fail(f"Second upload did not contend: {second.result()!r}")
                    time.sleep(0.01)
                self.assertTrue(blocked, "PostgreSQL did not observe common-student row-lock contention.")
            finally:
                release.set()
            first_id = first.result(timeout=15)
            second_id = second.result(timeout=15)

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(StudentDocument.objects.count(), 2)
        self.assertIsNotNone(StudentDocument.objects.get(pk=first_id).superseded_at)
        self.assertEqual(StudentDocument.objects.get(superseded_at__isnull=True).pk, second_id)
        self.assertEqual(len(list(self.storage_root.rglob("*.pdf"))), 2)
