from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import AdviserAssignment
from students.models import Student
from .models import StudentDocument
from django.test import SimpleTestCase
from .ocr import OcrResult
from .services import assess_quality



PDF_BYTES = b"%PDF-1.4\nsynthetic test document\n%%EOF\n"


def make_pdf():
    return SimpleUploadedFile("results.pdf", PDF_BYTES, content_type="application/pdf")


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class UploadTests(TestCase):
    def setUp(self):
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