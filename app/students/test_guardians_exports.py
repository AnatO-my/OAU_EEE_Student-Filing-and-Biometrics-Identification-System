import csv
import io

from django.contrib.auth.models import Permission
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User, AdviserAssignment
from .models import Student, Guardian


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class GuardianAndExportTests(APITestCase):
    def setUp(self):
        self.hod = User.objects.create_superuser("guardian-hod", "hod@example.test", "Example!1982-Birch")
        self.staff = User.objects.create_user("guardian-adviser", is_staff=True)
        self.students = [Student.objects.create(identifier_type="matriculation", identifier_value=f"000{i}",
            full_name=f"Example {i}", phone_number="08000000000", admission_year=2024,
            mode_of_admission="utme", current_level=level) for i, level in enumerate((300, 400))]
        AdviserAssignment.objects.create(staff=self.staff, academic_session="2026/2027", level=300)
        self.payload = {"full_name": "Example Guardian", "phone_number": "08000000001", "relationship": "Parent"}

    def grant(self, *codes):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="students", codename__in=codes))
        self.staff = User.objects.get(pk=self.staff.pk)
        self.client.force_authenticate(self.staff)

    def url(self, student=None):
        return reverse("guardian-list", kwargs={"student_id": (student or self.students[0]).pk})

    def test_assigned_staff_can_create_and_edit_without_relinking(self):
        self.grant("view_student", "view_guardian", "add_guardian", "change_guardian")
        response = self.client.post(self.url(), {**self.payload, "student": str(self.students[1].pk)}, format="json")
        self.assertEqual(response.status_code, 201)
        guardian = Guardian.objects.get()
        self.assertEqual(guardian.student_id, self.students[0].pk)
        detail = reverse("guardian-detail", kwargs={"student_id": self.students[0].pk, "guardian_id": guardian.pk})
        response = self.client.patch(detail, {"full_name": "Corrected", "student": str(self.students[1].pk)}, format="json")
        self.assertEqual(response.status_code, 200)
        guardian.refresh_from_db()
        self.assertEqual(guardian.full_name, "Corrected")
        self.assertEqual(guardian.student_id, self.students[0].pk)

    def test_out_of_scope_parent_and_detail_return_404(self):
        guardian = Guardian.objects.create(student=self.students[1], **self.payload)
        self.grant("view_student", "view_guardian", "add_guardian", "change_guardian")
        self.assertEqual(self.client.get(self.url(self.students[1])).status_code, 404)
        self.assertEqual(self.client.post(self.url(self.students[1]), self.payload, format="json").status_code, 404)
        detail = reverse("guardian-detail", kwargs={"student_id": self.students[0].pk, "guardian_id": guardian.pk})
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.patch(detail, {"full_name": "Bad"}, format="json").status_code, 404)

    def test_read_permission_does_not_grant_guardian_writes(self):
        self.grant("view_student", "view_guardian")
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.client.post(self.url(), self.payload, format="json").status_code, 403)
        self.assertFalse(Guardian.objects.exists())

    def test_revoked_assignment_blocks_guardian_access(self):
        self.grant("view_student", "view_guardian", "add_guardian")
        AdviserAssignment.objects.filter(staff=self.staff).update(is_active=False)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.post(self.url(), self.payload, format="json").status_code, 404)

    def test_student_cannot_write_guardian_records(self):
        self.client.force_authenticate(User.objects.create_user("guardian-student"))
        self.assertEqual(self.client.post(self.url(), self.payload, format="json").status_code, 403)

    def export_rows(self, response):
        return list(csv.DictReader(io.StringIO(b"".join(response.streaming_content).decode())))

    def test_export_requires_separate_permission_and_preserves_scope(self):
        self.grant("view_student")
        url = reverse("student-export")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.grant("export_student")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = self.export_rows(response)
        self.assertEqual([row["identifier_value"] for row in rows], ["0000"])
        self.assertNotIn("user", rows[0])
        self.assertNotIn("guardian", rows[0])

    def test_export_search_filters_and_formula_protection(self):
        self.students[0].full_name = "=DangerousCell()"
        self.students[0].save(update_fields=["full_name"])
        self.client.force_authenticate(self.hod)
        response = self.client.get(reverse("student-export"), {"current_level": 300, "search": "0000"})
        rows = self.export_rows(response)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "'=DangerousCell()")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_invalid_export_filter_returns_400(self):
        self.client.force_authenticate(self.hod)
        self.assertEqual(self.client.get(reverse("student-export"), {"current_level": "invalid"}).status_code, 400)
