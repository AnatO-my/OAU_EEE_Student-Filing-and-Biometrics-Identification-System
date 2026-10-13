from django.test import TestCase

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from students.models import Student

from .models import StudentDocument

PDF_BYTES = b"%PDF-1.4\nsynthetic test document\n%%EOF\n"


class UploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = get_user_model().objects.create_user(
            username="example-uploader",
            password="synthetic-test-password",
            is_staff=True,
        )
        self.student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="00123456",
            full_name="Example Student",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        self.url = f"/api/students/{self.student.student_id}/documents/"

    def test_staff_can_upload_a_pdf(self):
        self.client.force_authenticate(self.staff)
        pdf = SimpleUploadedFile("results.pdf", PDF_BYTES, content_type="application/pdf")
        response = self.client.post(self.url, {"file": pdf}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(StudentDocument.objects.count(), 1)
