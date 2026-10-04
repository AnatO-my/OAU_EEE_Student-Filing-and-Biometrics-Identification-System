from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Guardian, Student


class StudentAPItests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = get_user_model().objects.create_user(
            username="example-staff", password="synthetic-test-password", is_staff=True
        )
        self.student = Student.objects.create(
            identifier_type="matriculation", identifier_value="00123456",
            full_name="Example Student", phone_number="+2340000000000",
            admission_year=2024, mode_of_admission="utme", current_level=300,
        )

    def test_anonymous_and_nonstaff_are_denied(self):
        self.assertEqual(self.client.get("/api/students/").status_code, 403)
        user = get_user_model().objects.create_user(username="nonstaff")
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get("/api/students/").status_code, 403)

    def test_search_filters_and_detail(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get("/api/students/", {
            "search": "Example", "current_level": 300, "is_active": "true"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["identifier_value"], "00123456")
        self.assertEqual(self.client.get("/api/students/?current_level=200").data["count"], 0)
        detail = self.client.get(f"/api/students/{self.student.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(str(detail.data["student_id"]), str(self.student.pk))

    def test_invalid_filters_and_missing_student(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get("/api/students/?current_level=abc").status_code, 400)
        self.assertEqual(self.client.get("/api/students/?mode_of_admission=invalid").status_code, 400)
        self.assertEqual(self.client.get("/api/students/00000000-0000-0000-0000-000000000000/").status_code, 404)

    def test_pagination(self):
        self.client.force_authenticate(self.staff)
        Student.objects.bulk_create([
            Student(identifier_type="matriculation", identifier_value=f"TEST-{i}",
                    full_name=f"Student {i}", phone_number="+2340000000000",
                    admission_year=2024, mode_of_admission="utme", current_level=300)
            for i in range(20)
        ])
        response = self.client.get("/api/students/")
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(len(self.client.get("/api/students/?page=2").data["results"]), 1)

    def test_writes_not_yet_exposed(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post("/api/students/", {}, format="json").status_code, 405)

    def test_multiple_guardians_protect_student(self):
        for name in ["Guardian A", "Guardian B"]:
            Guardian.objects.create(student=self.student, full_name=name,
                                    relationship="Guardian", phone_number="+2340000000000")
        self.assertEqual(self.student.guardians.count(), 2)
        with self.assertRaises(ProtectedError):
            self.student.delete()

    def test_password_is_hashed(self):
        self.assertNotEqual(self.staff.password, "synthetic-test-password")
        self.assertTrue(self.staff.check_password("synthetic-test-password"))
