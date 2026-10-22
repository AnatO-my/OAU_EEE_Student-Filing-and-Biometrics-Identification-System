"""The database-selected calendar must govern all staff record surfaces."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import AdviserAssignment, AdviserMessage
from students.models import Guardian, Student
from documents.models import StudentDocument
from documents.test_storage import isolate_document_storage
from .current_session import current_session_name, current_session_state, select_current_session
from .models import AcademicSession, AcademicSessionSelection, Course, CourseOffering, Result


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class CurrentSessionIntegrationTests(TestCase):
    def setUp(self):
        isolate_document_storage(self)
        User = get_user_model()
        self.hod = User.objects.create_superuser("calendar-hod", "hod@example.invalid", "synthetic-password")
        self.staff = User.objects.create_user("calendar-adviser", is_staff=True)
        for app, codename in (
            ("students", "view_student"), ("students", "add_student"),
            ("students", "export_student"), ("students", "view_guardian"),
            ("students", "change_guardian"), ("academics", "view_result"),
            ("documents", "add_studentdocument"), ("accounts", "send_adviser_message"),
        ):
            self.staff.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
        self.old = AcademicSession.objects.create(name="2026/2027")
        self.new = AcademicSession.objects.create(name="2027/2028")
        self.old_assignment = AdviserAssignment.objects.create(staff=self.staff, academic_session=self.old.name, level=200)
        self.new_assignment = AdviserAssignment.objects.create(staff=self.staff, academic_session=self.new.name, level=300)
        self.old_student = self.student("SYN-OLD", 200)
        self.new_student = self.student("SYN-NEW", 300)
        self.old_guardian = Guardian.objects.create(student=self.old_student, full_name="Synthetic Old Guardian", relationship="Parent", phone_number="+2340000000000")
        self.new_guardian = Guardian.objects.create(student=self.new_student, full_name="Synthetic New Guardian", relationship="Parent", phone_number="+2340000000001")
        course = Course.objects.create(code="SYN201", title="Synthetic calendar course")
        for year, student in ((self.old, self.old_student), (self.new, self.new_student)):
            offering = CourseOffering.objects.create(course=course, academic_session=year, semester="harmattan", level=student.current_level, credit_units=3)
            Result.objects.create(student=student, offering=offering, score="70.00", credit_units=3)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def student(self, identifier, level):
        return Student.objects.create(identifier_type="matriculation", identifier_value=identifier,
            full_name=f"Synthetic {identifier}", phone_number="+2340000000000", admission_year=2024,
            mode_of_admission="utme", current_level=level)

    def select_new(self):
        select_current_session(user=self.hod, academic_session=self.new, expected_session_id=None)

    def test_environment_remains_the_bootstrap_fallback(self):
        self.assertEqual(current_session_state(), {"academic_session": None, "name": self.old.name, "source": "environment"})
        self.assertEqual(self.client.get("/api/auth/me/").json()["adviser_levels"], [200])
        self.assertEqual([row["student_id"] for row in self.client.get("/api/students/").json()["results"]], [str(self.old_student.pk)])

    def test_database_calendar_changes_identity_and_student_read_scope(self):
        self.select_new()
        self.assertEqual(current_session_name(), self.new.name)
        self.assertEqual(self.client.get("/api/auth/me/").json()["adviser_levels"], [300])
        self.assertEqual([row["student_id"] for row in self.client.get("/api/students/").json()["results"]], [str(self.new_student.pk)])
        self.assertEqual(self.client.get(f"/api/students/{self.old_student.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/students/{self.new_student.pk}/").status_code, 200)

    def test_csv_export_uses_the_same_selected_scope(self):
        self.select_new()
        response = self.client.get("/api/students/export/")
        self.assertEqual(response.status_code, 200)
        text = b"".join(response.streaming_content).decode()
        self.assertIn("SYN-NEW", text)
        self.assertNotIn("SYN-OLD", text)

    def test_academic_reads_and_guardians_follow_the_selected_calendar(self):
        self.select_new()
        rows = self.client.get("/api/results/").json()["results"]
        self.assertEqual([row["student"] for row in rows], [str(self.new_student.pk)])
        self.assertEqual(self.client.get(f"/api/students/{self.old_student.pk}/guardians/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/students/{self.new_student.pk}/guardians/").status_code, 200)
        url = f"/api/students/{self.new_student.pk}/guardians/{self.new_guardian.pk}/"
        self.assertEqual(self.client.patch(url, {"phone_number": "+2340000000002"}, format="json").status_code, 200)

    def test_document_upload_preserves_main_feature_but_uses_database_scope(self):
        self.select_new()
        def upload(student):
            return self.client.post(f"/api/students/{student.pk}/documents/", {
                "document_type": "result", "file": SimpleUploadedFile("synthetic.pdf", b"%PDF-1.4\nSynthetic review only\n%%EOF\n", content_type="application/pdf")
            }, format="multipart")
        self.assertEqual(upload(self.old_student).status_code, 404)
        accepted = upload(self.new_student)
        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(accepted.json()["student"], str(self.new_student.pk))
        self.assertEqual(StudentDocument.objects.count(), 1)

    def test_student_creation_requires_the_selected_adviser_assignment(self):
        self.select_new()
        data = {"identifier_type": "matriculation", "identifier_value": "SYN-CREATED", "full_name": "Synthetic New Record",
            "phone_number": "+2340000000000", "admission_year": 2024, "mode_of_admission": "utme", "current_level": 200}
        self.assertEqual(self.client.post("/api/students/", data, format="json").status_code, 403)
        data["current_level"] = 300
        self.assertEqual(self.client.post("/api/students/", data, format="json").status_code, 201)

    def test_messages_reject_old_assignment_and_snapshot_new_cohort(self):
        self.select_new()
        data = {"assignment_id": self.old_assignment.pk, "audience": "level", "subject": "Synthetic notice", "body": "Synthetic content"}
        self.assertEqual(self.client.post("/api/adviser-messages/", data, format="json").status_code, 403)
        data["assignment_id"] = self.new_assignment.pk
        self.assertEqual(self.client.post("/api/adviser-messages/", data, format="json").status_code, 201)
        self.assertEqual(list(AdviserMessage.objects.get().recipients.all()), [self.new_student])

    def test_stale_api_choice_preserves_selected_session_and_history(self):
        self.select_new()
        self.client.force_authenticate(self.hod)
        response = self.client.put("/api/academic-sessions/current/", {"academic_session": self.old.pk, "expected_session_id": None}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/academic-sessions/current/").json(), {"academic_session": self.new.pk, "name": self.new.name, "source": "database"})
        self.assertEqual(AcademicSessionSelection.objects.count(), 1)
