from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import AdviserAssignment
from students.models import Student
from .models import StudentDocument
from django.test import SimpleTestCase
from unittest.mock import patch
from .ocr import OcrResult
from .services import assess_quality
from .test_storage import isolate_document_storage



PDF_BYTES = b"%PDF-1.4\nsynthetic test document\n%%EOF\n"


def make_pdf():
    return SimpleUploadedFile("results.pdf", PDF_BYTES, content_type="application/pdf")
def clear_scan_ocr(path):
    return OcrResult(text="Course results " * 20, confidence=91.0)


def blurry_scan_ocr(path):
    return OcrResult(text="Course results " * 20, confidence=32.0)

@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class UploadTests(TestCase):
    def setUp(self):
        self.storage_root = isolate_document_storage(self)
        self.client = APIClient()
        self.staff = get_user_model().objects.create_user(
            username="example-uploader",
            password="synthetic-test-password",
            is_staff=True,
        )
        AdviserAssignment.objects.create(
            staff=self.staff, academic_session="2026/2027", level=300
        )
        for app_label, codename in [
            ("students", "view_student"),
            ("documents", "add_studentdocument"),
        ]:
            self.staff.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )
        self.student = self.make_student("00123456", 300)
        self.url = f"/api/students/{self.student.student_id}/documents/"

    def make_student(self, identifier, level):
        return Student.objects.create(
            identifier_type="matriculation",
            identifier_value=identifier,
            full_name=f"Example Student {identifier}",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=level,
        )

    def post_pdf(self, url=None):
        return self.client.post(url or self.url, {"file": make_pdf(), "document_type": "result"}, format="multipart")

    def test_staff_can_upload_a_pdf(self):
        self.client.force_authenticate(self.staff)
        response = self.post_pdf()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(StudentDocument.objects.count(), 1)
        document = StudentDocument.objects.get()
        self.assertTrue(document.file.storage.path(document.file.name).startswith(str(self.storage_root)))
        self.assertTrue(document.file.storage.exists(document.file.name))

    def test_staff_deactivated_during_ocr_cannot_save_the_upload(self):
        self.client.force_authenticate(self.staff)

        def deactivate(path):
            get_user_model().objects.filter(pk=self.staff.pk).update(is_active=False)
            return clear_scan_ocr(path)

        with patch("documents.services.run_ocr", side_effect=deactivate):
            response = self.post_pdf()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(StudentDocument.objects.count(), 0)
        self.assertEqual(list(self.storage_root.rglob("*")), [])

    def test_upload_permission_revoked_during_ocr_is_rechecked(self):
        self.client.force_authenticate(self.staff)

        def revoke(path):
            self.staff.user_permissions.remove(Permission.objects.get(
                content_type__app_label="documents", codename="add_studentdocument"))
            return clear_scan_ocr(path)

        with patch("documents.services.run_ocr", side_effect=revoke):
            response = self.post_pdf()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(StudentDocument.objects.count(), 0)

    def test_assignment_removed_during_ocr_is_rechecked(self):
        self.client.force_authenticate(self.staff)

        def revoke(path):
            AdviserAssignment.objects.filter(staff=self.staff).delete()
            return clear_scan_ocr(path)

        with patch("documents.services.run_ocr", side_effect=revoke):
            response = self.post_pdf()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(StudentDocument.objects.count(), 0)

    def test_student_moved_during_ocr_is_rechecked(self):
        self.client.force_authenticate(self.staff)

        def move(path):
            Student.objects.filter(pk=self.student.pk).update(current_level=100)
            return clear_scan_ocr(path)

        with patch("documents.services.run_ocr", side_effect=move):
            response = self.post_pdf()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(StudentDocument.objects.count(), 0)

    def test_anonymous_and_nonstaff_are_denied(self):
        self.assertEqual(self.post_pdf().status_code, 403)
        user = get_user_model().objects.create_user(username="nonstaff")
        self.client.force_authenticate(user)
        self.assertEqual(self.post_pdf().status_code, 403)

    def test_staff_without_add_permission_is_denied(self):
        self.staff.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="documents", codename="add_studentdocument"
            )
        )
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.post_pdf().status_code, 403)
        self.assertEqual(StudentDocument.objects.count(), 0)

    def test_student_outside_staff_scope_is_not_found(self):
        other = self.make_student("00999999", 100)
        self.client.force_authenticate(self.staff)
        response = self.post_pdf(f"/api/students/{other.student_id}/documents/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(StudentDocument.objects.count(), 0)
    def test_clear_scan_is_accepted(self):
        self.client.force_authenticate(self.staff)
        with self.settings(DOCUMENT_OCR_BACKEND="documents.tests.clear_scan_ocr"):
            response = self.post_pdf()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "accepted")

    def test_blurry_scan_is_rejected_and_not_saved(self):
        self.client.force_authenticate(self.staff)
        with self.settings(DOCUMENT_OCR_BACKEND="documents.tests.blurry_scan_ocr"):
            response = self.post_pdf()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(StudentDocument.objects.count(), 0)

    def test_unavailable_ocr_keeps_file_for_review(self):
        self.client.force_authenticate(self.staff)
        response = self.post_pdf()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "needs_review")

    def test_new_upload_supersedes_the_old_one(self):
        self.client.force_authenticate(self.staff)
        with self.settings(DOCUMENT_OCR_BACKEND="documents.tests.clear_scan_ocr"):
            self.post_pdf()
            self.post_pdf()
        self.assertEqual(StudentDocument.objects.count(), 2)
        self.assertEqual(
            StudentDocument.objects.filter(superseded_at__isnull=True).count(), 1
        )

    def test_rejected_rescan_keeps_the_old_document_current(self):
        self.client.force_authenticate(self.staff)
        with self.settings(DOCUMENT_OCR_BACKEND="documents.tests.clear_scan_ocr"):
            self.assertEqual(self.post_pdf().status_code, 201)
        with self.settings(DOCUMENT_OCR_BACKEND="documents.tests.blurry_scan_ocr"):
            self.assertEqual(self.post_pdf().status_code, 422)
        self.assertEqual(StudentDocument.objects.count(), 1)
        self.assertEqual(
            StudentDocument.objects.filter(superseded_at__isnull=True).count(), 1
        )
    def test_document_type_is_required(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self.url, {"file": make_pdf()}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(StudentDocument.objects.count(), 0)

    def test_renamed_file_is_rejected(self):
        self.client.force_authenticate(self.staff)
        fake = SimpleUploadedFile("results.pdf", b"MZ not really a pdf")
        response = self.client.post(
            self.url, {"file": fake, "document_type": "result"}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
class QualityGateTests(SimpleTestCase):
    def test_clear_scan_is_accepted(self):
        decision = assess_quality(OcrResult(text="Course results " * 20, confidence=91))
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.status, "accepted")

    def test_low_confidence_is_rejected(self):
        decision = assess_quality(OcrResult(text="Course results " * 20, confidence=32))
        self.assertFalse(decision.accepted)

    def test_almost_no_text_is_rejected(self):
        decision = assess_quality(OcrResult(text="   ", confidence=95))
        self.assertFalse(decision.accepted)

    def test_missing_confidence_is_judged_on_text_alone(self):
        decision = assess_quality(OcrResult(text="Course results " * 20))
        self.assertTrue(decision.accepted)
