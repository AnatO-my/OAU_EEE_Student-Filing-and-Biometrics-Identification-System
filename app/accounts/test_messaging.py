from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from students.models import Student
from .models import User, AdviserAssignment, AdviserMessage, HODMessage
from .services import send_adviser_message, send_hod_message


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class MessagingIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_superuser("hod", "hod@example.com", "test-password")
        self.adviser = User.objects.create_user("adviser", is_staff=True)
        self.adviser.user_permissions.add(Permission.objects.get(
            content_type__app_label="accounts", codename="send_adviser_message"))
        self.assignment = AdviserAssignment.objects.create(
            staff=self.adviser, academic_session="2026/2027", level=300)
        self.other_staff = User.objects.create_user("other-adviser", is_staff=True)
        AdviserAssignment.objects.create(
            staff=self.other_staff, academic_session="2026/2027", level=400)
        self.student_user = User.objects.create_user("student", password="student-password")
        self.other_user = User.objects.create_user("other-student")
        self.student = self.make_student("S-001", 300, self.student_user)
        self.other_student = self.make_student("S-002", 400, self.other_user)

    def make_student(self, identifier, level, user=None, is_active=True):
        return Student.objects.create(
            identifier_type="matriculation", identifier_value=identifier,
            full_name=identifier, phone_number="+2340000000000", admission_year=2024,
            mode_of_admission="utme", current_level=level, user=user, is_active=is_active)

    def post(self, audience, **target):
        return self.client.post("/api/hod-messages/", {
            "audience": audience, "subject": "Meeting", "body": "Please attend.", **target,
        }, format="json")

    def test_anonymous_student_and_staff_cannot_send_hod_messages(self):
        for user in [None, self.student_user, self.adviser]:
            self.client.force_authenticate(user)
            self.assertEqual(self.post("individual", recipient_id=str(self.student.pk)).status_code, 403)
        self.assertEqual(HODMessage.objects.count(), 0)

    def test_service_rejects_nonhod_direct_call(self):
        for user in [AnonymousUser(), self.adviser, self.student_user]:
            with self.assertRaises(PermissionDenied):
                send_hod_message(user=user, validated_data={
                    "audience": "individual", "recipient_id": self.student.pk,
                    "subject": "Meeting", "body": "Please attend."})
        self.assertEqual(HODMessage.objects.count(), 0)

    def test_hod_sends_individual_message_without_assignment(self):
        self.client.force_authenticate(self.hod)
        response = self.post("individual", recipient_id=str(self.student.pk))
        self.assertEqual(response.status_code, 201)
        message = HODMessage.objects.get(pk=response.data["message_id"])
        self.assertEqual(message.sender, self.hod)
        self.assertEqual(message.academic_session, "2026/2027")
        self.assertSetEqual(set(message.recipients.all()), {self.student})
        self.assertEqual(message.adviser_recipients.count(), 0)

    def test_level_message_excludes_other_level_and_inactive_students(self):
        self.make_student("INACTIVE", 300, is_active=False)
        second = self.make_student("S-003", 300)
        self.client.force_authenticate(self.hod)
        response = self.post("level", level=300)
        self.assertEqual(response.status_code, 201)
        message = HODMessage.objects.get(pk=response.data["message_id"])
        self.assertSetEqual(set(message.recipients.all()), {self.student, second})

    def test_adviser_message_only_targets_current_assigned_staff(self):
        self.client.force_authenticate(self.hod)
        response = self.post("adviser", adviser_id=self.adviser.pk)
        self.assertEqual(response.status_code, 201)
        message = HODMessage.objects.get(pk=response.data["message_id"])
        self.assertSetEqual(set(message.adviser_recipients.all()), {self.adviser})
        self.assertEqual(message.recipients.count(), 0)
        self.assignment.is_active = False
        self.assignment.save(update_fields=["is_active"])
        self.assertEqual(self.post("adviser", adviser_id=self.adviser.pk).status_code, 400)
        self.assertEqual(HODMessage.objects.count(), 1)

    def test_invalid_and_conflicting_targets_do_not_save_messages(self):
        self.client.force_authenticate(self.hod)
        for audience, target in [
            ("individual", {}), ("adviser", {}), ("level", {}),
            ("level", {"level": 300, "recipient_id": str(self.student.pk)}),
            ("adviser", {"adviser_id": self.student_user.pk}),
            ("level", {"level": 0}), ("level", {"level": 999}),
            ("individual", {"recipient_id": "invalid"}),
        ]:
            self.assertEqual(self.post(audience, **target).status_code, 400)
        self.assertEqual(HODMessage.objects.count(), 0)

    @override_settings(CURRENT_ACADEMIC_SESSION="")
    def test_missing_session_rejects_hod_sending(self):
        self.client.force_authenticate(self.hod)
        self.assertEqual(self.post("level", level=300).status_code, 403)
        self.assertEqual(HODMessage.objects.count(), 0)

    def test_hod_session_post_requires_csrf(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.hod)
        self.assertEqual(self.post("level", level=300).status_code, 403)
        self.assertEqual(HODMessage.objects.count(), 0)
        token = self.client.get("/api/auth/csrf/").data["csrfToken"]
        response = self.client.post("/api/hod-messages/", {
            "audience": "level", "level": 300, "subject": "Meeting", "body": "Please attend.",
        }, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)

    def test_hod_inbox_only_returns_saved_recipients(self):
        self.client.force_authenticate(self.hod)
        self.post("individual", recipient_id=str(self.student.pk))
        self.post("adviser", adviser_id=self.adviser.pk)
        for user, count in [(self.student_user, 1), (self.other_user, 0),
                            (self.adviser, 1), (self.other_staff, 0)]:
            self.client.force_authenticate(user)
            response = self.client.get("/api/me/hod-messages/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], count)
            for row in response.data["results"]:
                self.assertNotIn("recipients", row)
                self.assertNotIn("adviser_recipients", row)
        self.student.current_level = 400
        self.student.save(update_fields=["current_level"])
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.get("/api/me/hod-messages/").data["count"], 1)

    def test_adviser_inbox_is_isolated_and_read_only(self):
        message = send_adviser_message(user=self.adviser, validated_data={
            "assignment_id": self.assignment.pk, "audience": "individual",
            "recipient_id": self.student.pk, "subject": "Meeting", "body": "Please attend."})
        self.client.force_authenticate(self.student_user)
        response = self.client.get("/api/me/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], message.pk)
        self.assertNotIn("recipients", response.data["results"][0])
        self.assertEqual(self.client.post("/api/me/messages/", {}).status_code, 405)
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get("/api/me/messages/").data["count"], 0)
        self.client.force_authenticate(self.adviser)
        self.assertEqual(self.client.get("/api/me/messages/").status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/me/messages/").status_code, 403)
