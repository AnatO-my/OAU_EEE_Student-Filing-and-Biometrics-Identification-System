from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied

from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.test import APIClient

from students.models import Student
from .models import AdviserAssignment, User, AdviserMessage
from .services import send_adviser_message


class AdviserAssignmentValidationTests(SimpleTestCase):
    def assignment(self, **changes):
        values = {
            "academic_session": "2026/2027",
            "level": 300,
        }
        values.update(changes)
        return AdviserAssignment(**values)

    def test_valid_session_is_accepted(self):
        self.assignment().clean()

    def test_invalid_session_format_is_rejected(self):
        with self.assertRaises(ValidationError) as error:
            self.assignment(academic_session="2026-2027").clean()

        self.assertIn("academic_session", error.exception.message_dict)

    def test_nonconsecutive_years_are_rejected(self):
        with self.assertRaises(ValidationError) as error:
            self.assignment(academic_session="2026/2028").clean()

        self.assertIn("academic_session", error.exception.message_dict)

    def test_zero_level_is_rejected(self):
        with self.assertRaises(ValidationError) as error:
            self.assignment(level=0).clean()

        self.assertIn("level", error.exception.message_dict)

    def test_nonstaff_account_is_rejected(self):
        user = User(pk=1, username="example-student", is_staff=False)

        with self.assertRaises(ValidationError) as error:
            self.assignment(staff=user).clean()

        self.assertIn("staff", error.exception.message_dict)


class AdviserMessageTests(TestCase):
    def test_level_change_preserves_existing_message(self):
        adviser = User.objects.create_user(
            username="example-adviser",
            is_staff=True,
        )
        assignment = AdviserAssignment.objects.create(
            staff=adviser,
            academic_session="2026/2027",
            level=300,
        )
        student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="TEST-001",
            full_name="Example Student",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        message = AdviserMessage.objects.create(
            assignment=assignment,
            audience=AdviserMessage.Audience.LEVEL,
            subject="Advising meeting",
            body="Please attend the scheduled meeting.",
        )
        message.recipients.add(student)

        student.current_level = 400
        student.save(update_fields=["current_level"])

        self.assertTrue(message.recipients.filter(pk=student.pk).exists())
        self.assertTrue(student.adviser_messages.filter(pk=message.pk).exists())


class CSRFEnforcementTests(TestCase):
    # class that proves the unsafe endpoints still reject requests that arrive without
    # the csrf token, django test client skips csrf checks by default so this is turned
    # back on explicitly here
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.staff = get_user_model().objects.create_user(
            username="example-staff",
            password="synthetic-test-password",
            is_staff=True,
        )

        from django.contrib.auth.models import Permission

        self.staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="students", codename="view_student"
            )
        )

    def test_logout_without_csrf_token_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 403)

    def test_student_reads_without_csrf_token_still_succeed(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)

    def test_login_without_a_prior_csrf_token_is_rejected(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "example-staff", "password": "synthetic-test-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_login_with_csrf_token_succeeds(self):
        token = self.client.get("/api/auth/csrf/").data["csrfToken"]
        response = self.client.post(
            "/api/auth/login/",
            {"username": "example-staff", "password": "synthetic-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)


class AuthEndpointTests(TestCase):
    # class covering the JSON login, logout, current user, and csrf endpoints that the
    # React client needs before it can read any staff data
    def setUp(self):
        self.client = APIClient()
        self.staff = get_user_model().objects.create_user(
            username="example-staff",
            password="synthetic-test-password",
            is_staff=True,
        )
        self.nonstaff = get_user_model().objects.create_user(
            username="example-nonstaff",
            password="synthetic-test-password",
        )

    # method that signs a staff member in through the JSON endpoint
    def _login(self):
        return self.client.post(
            "/api/auth/login/",
            {"username": "example-staff", "password": "synthetic-test-password"},
            format="json",
        )

    def test_csrf_endpoint_issues_a_token_and_cookie(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["csrfToken"])
        self.assertIn("csrftoken", response.cookies)

    def test_login_returns_identity_and_starts_a_session(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "example-staff")
        self.assertTrue(response.data["is_staff"])
        self.assertNotIn("password", response.data)
        self.assertIn("sessionid", self.client.cookies)

    def test_login_rejects_a_wrong_password(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "example-staff", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sessionid", self.client.cookies)

    def test_login_rejects_nonstaff_and_unknown_accounts_identically(self):
        nonstaff = self.client.post(
            "/api/auth/login/",
            {"username": "example-nonstaff", "password": "synthetic-test-password"},
            format="json",
        )
        unknown = self.client.post(
            "/api/auth/login/",
            {"username": "no-such-account", "password": "synthetic-test-password"},
            format="json",
        )
        self.assertEqual(nonstaff.status_code, 400)
        self.assertEqual(nonstaff.data, unknown.data)
        self.assertNotIn("sessionid", self.client.cookies)

    def test_login_requires_both_credentials(self):
        response = self.client.post("/api/auth/login/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("password", response.data)

    def test_current_user_requires_an_authenticated_staff_session(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)
        self.client.force_authenticate(self.nonstaff)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_current_user_reports_the_signed_in_staff(self):
        self._login()
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "example-staff")
        self.assertTrue(response.data["is_staff"])

    def test_logout_ends_the_session(self):
        self._login()
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class AdviserMessageSendingTests(TestCase):
    def setUp(self):
        self.adviser = User.objects.create_user(
            username="sending-adviser",
            is_staff=True,
        )
        permission = Permission.objects.get(
            content_type__app_label="accounts",
            codename="send_adviser_message",
        )
        self.adviser.user_permissions.add(permission)

        self.assignment = AdviserAssignment.objects.create(
            staff=self.adviser,
            academic_session="2026/2027",
            level=300,
        )
        self.student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="MESSAGE-001",
            full_name="Example Recipient",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )

    def test_sending_without_permission_is_rejected(self):
        self.adviser.user_permissions.clear()

        # Reload the account to avoid cached permission results.
        adviser = User.objects.get(pk=self.adviser.pk)

        with self.assertRaises(PermissionDenied):
            send_adviser_message(
                user=adviser,
                validated_data={
                    "assignment_id": self.assignment.pk,
                    "audience": AdviserMessage.Audience.INDIVIDUAL,
                    "recipient_id": self.student.pk,
                    "subject": "Meeting",
                    "body": "Please attend.",
                },
            )

        self.assertEqual(AdviserMessage.objects.count(), 0)

    def test_individual_message_outside_assigned_level_is_rejected(self):
        self.student.current_level = 400
        self.student.save(update_fields=["current_level"])

        with self.assertRaises(APIValidationError):
            send_adviser_message(
                user=self.adviser,
                validated_data={
                    "assignment_id": self.assignment.pk,
                    "audience": AdviserMessage.Audience.INDIVIDUAL,
                    "recipient_id": self.student.pk,
                    "subject": "Individual meeting",
                    "body": "Please attend.",
                },
            )

        self.assertEqual(AdviserMessage.objects.count(), 0)

    def test_another_advisers_assignment_is_rejected(self):
        other_adviser = User.objects.create_user(
            username="other-adviser",
            is_staff=True,
        )
        other_assignment = AdviserAssignment.objects.create(
            staff=other_adviser,
            academic_session="2026/2027",
            level=300,
        )

        with self.assertRaises(PermissionDenied):
            send_adviser_message(
                user=self.adviser,
                validated_data={
                    "assignment_id": other_assignment.pk,
                    "audience": AdviserMessage.Audience.INDIVIDUAL,
                    "recipient_id": self.student.pk,
                    "subject": "Meeting",
                    "body": "Please attend.",
                },
            )

        self.assertEqual(AdviserMessage.objects.count(), 0)

    def test_send_individual_message(self):
        message = send_adviser_message(
            user=self.adviser,
            validated_data={
                "assignment_id": self.assignment.pk,
                "audience": AdviserMessage.Audience.INDIVIDUAL,
                "recipient_id": self.student.pk,
                "subject": "Advising meeting",
                "body": "Please attend the scheduled meeting.",
            },
        )

        message.refresh_from_db()
        self.assertEqual(message.assignment, self.assignment)
        self.assertEqual(message.subject, "Advising meeting")
        self.assertEqual(message.recipients.count(), 1)
        self.assertTrue(message.recipients.filter(pk=self.student.pk).exists())

    def test_level_announcement_reaches_only_active_assigned_students(self):
        def create_student(identifier, level=300, is_active=True):
            return Student.objects.create(
                identifier_type="matriculation",
                identifier_value=identifier,
                full_name=f"Student {identifier}",
                phone_number="+2340000000000",
                admission_year=2024,
                mode_of_admission="utme",
                current_level=level,
                is_active=is_active,
            )

        second = create_student("MESSAGE-002")
        create_student("OTHER-LEVEL", level=400)
        create_student("INACTIVE", is_active=False)

        message = send_adviser_message(
            user=self.adviser,
            validated_data={
                "assignment_id": self.assignment.pk,
                "audience": AdviserMessage.Audience.LEVEL,
                "subject": "Level meeting",
                "body": "Please attend the level meeting.",
            },
        )

        self.assertSetEqual(
            set(message.recipients.values_list("pk", flat=True)),
            {self.student.pk, second.pk},
        )

    def test_revoked_and_previous_session_assignments_are_rejected(self):
        cases = [
            {"is_active": False, "academic_session": "2026/2027"},
            {"is_active": True, "academic_session": "2025/2026"},
        ]

        for changes in cases:
            with self.subTest(**changes):
                AdviserAssignment.objects.filter(pk=self.assignment.pk).update(
                    **changes
                )

                with self.assertRaises(PermissionDenied):
                    send_adviser_message(
                        user=self.adviser,
                        validated_data={
                            "assignment_id": self.assignment.pk,
                            "audience": AdviserMessage.Audience.LEVEL,
                            "subject": "Level meeting",
                            "body": "Please attend.",
                        },
                    )

                self.assertEqual(AdviserMessage.objects.count(), 0)

    def test_api_sends_individual_message(self):
        client = APIClient()
        client.force_authenticate(self.adviser)

        response = client.post(
            "/api/adviser-messages/",
            {
                "assignment_id": self.assignment.pk,
                "audience": "individual",
                "recipient_id": str(self.student.pk),
                "subject": "Advising meeting",
                "body": "Please attend the scheduled meeting.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["recipient_count"], 1)

        message = AdviserMessage.objects.get(pk=response.data["message_id"])
        self.assertEqual(message.assignment, self.assignment)
        self.assertEqual(
            message.body,
            "Please attend the scheduled meeting.",
        )
        self.assertSetEqual(
            set(message.recipients.values_list("pk", flat=True)),
            {self.student.pk},
        )

    def test_session_sending_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.adviser)

        payload = {
            "assignment_id": self.assignment.pk,
            "audience": "individual",
            "recipient_id": str(self.student.pk),
            "subject": "Advising meeting",
            "body": "Please attend.",
        }

        response = client.post(
            "/api/adviser-messages/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AdviserMessage.objects.count(), 0)

        token = client.get("/api/auth/csrf/").data["csrfToken"]

        response = client.post(
            "/api/adviser-messages/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(AdviserMessage.objects.count(), 1)