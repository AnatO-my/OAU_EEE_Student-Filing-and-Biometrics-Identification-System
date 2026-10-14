import uuid
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import User, AdviserAssignment
from .models import Student


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class HODLevelTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_superuser(
            "level-hod", "hod@example.com", "test-password"
        )
        self.staff = User.objects.create_user("level-adviser", is_staff=True)
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="students",
                codename__in=["view_student", "change_student"],
            )
        )
        for level in [300, 400]:
            AdviserAssignment.objects.create(
                staff=self.staff, academic_session="2026/2027", level=level
            )
        self.students = [
            Student.objects.create(
                identifier_type="matriculation",
                identifier_value=f"LEVEL-{i}",
                full_name=f"Student {i}",
                phone_number="+2340000000000",
                admission_year=2024,
                mode_of_admission="utme",
                current_level=300,
            )
            for i in range(2)
        ]
        self.payload = {
            "student_ids": [str(s.pk) for s in self.students],
            "expected_level": 300,
            "current_level": 400,
        }

    def test_adviser_cannot_change_level_even_with_both_assignments(self):
        self.client.force_authenticate(self.staff)
        response = self.client.patch(
            f"/api/students/{self.students[0].pk}/",
            {"current_level": 400, "full_name": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.students[0].refresh_from_db()
        self.assertEqual(self.students[0].current_level, 300)
        self.assertEqual(self.students[0].full_name, "Student 0")

    def test_hod_can_change_one_student(self):
        self.client.force_authenticate(self.hod)
        response = self.client.patch(
            f"/api/students/{self.students[0].pk}/",
            {"current_level": 400},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.students[0].refresh_from_db()
        self.assertEqual(self.students[0].current_level, 400)

    def test_bulk_change_updates_only_selected_students(self):
        self.client.force_authenticate(self.hod)
        payload = {**self.payload, "student_ids": [str(self.students[0].pk)]}
        response = self.client.post(
            "/api/students/bulk-level-change/", payload, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated_count"], 1)
        for student, level in zip(self.students, [400, 300]):
            student.refresh_from_db()
            self.assertEqual(student.current_level, level)

    def test_bulk_failure_saves_no_partial_changes(self):
        self.client.force_authenticate(self.hod)
        for changes in [
            {"student_ids": self.payload["student_ids"] + [str(uuid.uuid4())]},
            {"expected_level": 200},
            {"student_ids": [str(self.students[0].pk)] * 2},
            {"student_ids": []},
            {"current_level": 0},
        ]:
            response = self.client.post(
                "/api/students/bulk-level-change/",
                {**self.payload, **changes},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(Student.objects.filter(current_level=300).count(), 2)

    def test_bulk_is_hod_only(self):
        for user in [None, self.staff, User.objects.create_user("level-student")]:
            self.client.force_authenticate(user)
            self.assertEqual(
                self.client.post(
                    "/api/students/bulk-level-change/", self.payload, format="json"
                ).status_code,
                403,
            )
        self.assertEqual(Student.objects.filter(current_level=300).count(), 2)

    def test_bulk_session_requires_csrf(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.hod)
        self.assertEqual(
            self.client.post(
                "/api/students/bulk-level-change/", self.payload, format="json"
            ).status_code,
            403,
        )
        token = self.client.get("/api/auth/csrf/").data["csrfToken"]
        response = self.client.post(
            "/api/students/bulk-level-change/",
            self.payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated_count"], 2)

    def test_adviser_cannot_mark_student_as_graduated(self):
        self.client.force_authenticate(self.staff)

        response = self.client.patch(
            f"/api/students/{self.students[0].pk}/",
            {
                "academic_status": "graduated",
                "full_name": "Changed Name",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.students[0].refresh_from_db()
        self.assertEqual(
            self.students[0].academic_status,
            Student.AcademicStatus.UNDERGRADUATE,
        )
        self.assertEqual(self.students[0].full_name, "Student 0")

    def test_hod_cannot_graduate_student_without_verified_cgpa(self):
        self.client.force_authenticate(self.hod)

        response = self.client.patch(
            f"/api/students/{self.students[0].pk}/",
            {"academic_status": "graduated"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("academic_status", response.data)

        self.students[0].refresh_from_db()
        self.assertEqual(
            self.students[0].academic_status,
            Student.AcademicStatus.UNDERGRADUATE,
        )
        self.assertEqual(self.students[0].current_level, 300)

    def test_bulk_graduation_without_verified_cgpa_changes_nothing(self):
        self.client.force_authenticate(self.hod)

        response = self.client.post(
            "/api/students/bulk-status-change/",
            {
                "student_ids": [str(student.pk) for student in self.students],
                "expected_status": "undergraduate",
                "academic_status": "graduated",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("academic_status", response.data)

        for student in self.students:
            student.refresh_from_db()
            self.assertEqual(
                student.academic_status,
                Student.AcademicStatus.UNDERGRADUATE,
            )
            self.assertEqual(student.current_level, 300)
