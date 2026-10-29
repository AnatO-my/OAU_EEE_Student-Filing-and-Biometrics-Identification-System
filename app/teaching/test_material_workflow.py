"""Exercise actual multipart requests and byte-preserving private downloads."""
import hashlib
import uuid
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from attendance import tests as attendance_fixtures
from attendance.services import assign_staff, confirm_roster
from .models import Material, MaterialVersion


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class MaterialWorkflowTests(TestCase):
    make_student = attendance_fixtures.AttendanceTests.make_student

    def setUp(self):
        attendance_fixtures.AttendanceTests.setUp(self)
        self.staff.user_permissions.add(Permission.objects.get(codename="manage_material", content_type__app_label="teaching"))
        confirm_roster(user=self.hod, offering=self.offering, student_ids=[self.student.pk], expected_revision=0)
        storage_root = TemporaryDirectory()
        self.addCleanup(storage_root.cleanup)
        storage_patch = patch.object(MaterialVersion._meta.get_field("file"), "storage", FileSystemStorage(location=storage_root.name))
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        self.bytes = b"%PDF-1.4\nSynthetic course notes\n%%EOF"

    def payload(self, **changes):
        return {"event_id": str(uuid.uuid4()), "offering": self.offering.pk,
                "title": "Circuit notes", "reason": "Lecture resource", "expected_version": 0,
                "withdrawn": "false", "upload": SimpleUploadedFile("notes.pdf", self.bytes), **changes}

    def post(self, **changes):
        self.client.force_authenticate(self.staff)
        response = self.client.post("/api/teaching/materials/", self.payload(**changes), format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def download(self, path, expected):
        response = self.client.get(path, HTTP_ACCEPT="*/*")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), expected)
        response.close()

    def test_multipart_upload_lists_and_downloads_exact_bytes_for_rostered_student(self):
        row = self.post()
        version = MaterialVersion.objects.get()
        self.assertEqual(version.sha256, hashlib.sha256(self.bytes).hexdigest())
        self.assertEqual(version.actor_id, self.staff.pk)
        self.assertEqual(version.material.offering_id, self.offering.pk)
        self.client.force_authenticate(self.user)
        listing = self.client.get("/api/teaching/materials/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data, [row])
        self.download(row["download_url"], self.bytes)

    def test_generic_file_download_accepts_portal_wildcard_header(self):
        row = self.post()
        self.client.force_authenticate(self.user)
        response = self.client.get(row["download_url"], HTTP_ACCEPT="*/*")
        try:
            self.assertEqual(response.status_code, 200)
        finally:
            response.close()

    def test_student_and_unassigned_staff_cannot_post_or_read_course_material(self):
        row = self.post()
        self.other.user_permissions.add(Permission.objects.get(codename="manage_material", content_type__app_label="teaching"))
        for account in (self.user, self.other):
            self.client.force_authenticate(account)
            self.assertEqual(self.client.post("/api/teaching/materials/", self.payload(), format="multipart").status_code, 403)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/teaching/materials/").data, [])
        self.assertEqual(self.client.get(row["download_url"]).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(row["download_url"]).status_code, 403)
        self.assertEqual(Material.objects.count(), 1)

    def test_permissions_assignment_and_roster_changes_take_effect(self):
        row = self.post()
        confirm_roster(user=self.hod, offering=self.offering, student_ids=[self.retaker.pk], expected_revision=1)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/teaching/materials/").data, [])
        self.assertEqual(self.client.get(row["download_url"]).status_code, 403)
        assign_staff(user=self.hod, offering=self.offering, staff=self.staff, is_active=False)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post("/api/teaching/materials/", self.payload(), format="multipart").status_code, 403)

    def test_exact_post_retry_does_not_duplicate_material(self):
        event = str(uuid.uuid4())
        first = self.post(event_id=event)
        second = self.post(event_id=event)
        self.assertEqual(first, second)
        self.assertEqual(Material.objects.count(), 1)
        self.assertEqual(MaterialVersion.objects.count(), 1)

    def test_multipart_replacement_rejects_stale_update_and_preserves_archive(self):
        row = self.post()
        url = f"/api/teaching/materials/{row['id']}/"
        revised = b"%PDF-1.4\nRevised notes\n%%EOF"
        self.client.force_authenticate(self.staff)
        response = self.client.put(url, self.payload(expected_version=1, upload=SimpleUploadedFile("revised.pdf", revised)), format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        current = response.data
        stale = self.client.put(url, self.payload(expected_version=1), format="multipart")
        self.assertEqual(stale.status_code, 400)
        self.download(row["download_url"], self.bytes)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(row["download_url"]).status_code, 403)
        self.download(current["download_url"], revised)
        self.assertEqual(MaterialVersion.objects.count(), 2)

    def test_invalid_uploads_are_rejected_without_creating_material(self):
        self.client.force_authenticate(self.staff)
        for filename, data in (("fake.pdf", b"not a PDF"), ("run.exe", b"binary"), ("empty.txt", b"")):
            response = self.client.post("/api/teaching/materials/", self.payload(upload=SimpleUploadedFile(filename, data)), format="multipart")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Material.objects.exists())
