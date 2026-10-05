from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from .models import AdviserAssignment, User, AdviserMessage
from students.models import Student


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
    #class that proves the unsafe endpoints still reject requests that arrive without
    #the csrf token, django test client skips csrf checks by default so this is turned
    #back on explicitly here
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.staff = get_user_model().objects.create_user(
            username="example-staff",
            password="synthetic-test-password",
            is_staff=True,
        )

        from django.contrib.auth.models import Permission
        self.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="students", codename="view_student"
        ))

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
            format="json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)


class AuthEndpointTests(TestCase):
    #class covering the JSON login, logout, current user, and csrf endpoints that the
    #React client needs before it can read any staff data
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

    #method that signs a staff member in through the JSON endpoint
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

    def test_current_user_requires_an_authenticated_session(self):
        #an anonymous caller is refused, but any authenticated account may read its own
        #identity now that students can sign in too
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)
        self.client.force_authenticate(self.nonstaff)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "example-nonstaff")
        self.assertFalse(response.data["is_staff"])
        self.assertNotIn("password", response.data)

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
class StudentLoginTests(TestCase):
    #class covering student sign in and the session it receives, it uses the real csrf
    #and session endpoints rather than forced authentication so the whole browser flow
    #is exercised
    def setUp(self):
        self.client = APIClient()
        self.student_user = User.objects.create_user(
            username="example-student",
            password="synthetic-test-password",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            identifier_type="matriculation",
            identifier_value="TEST-STUDENT-001",
            full_name="Example Student",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        self.staff = User.objects.create_user(
            username="example-staff-login",
            password="synthetic-test-password",
            is_staff=True,
        )
        self.unlinked = User.objects.create_user(
            username="example-unlinked",
            password="synthetic-test-password",
        )

    #method that signs an account in through the real endpoint, obtaining the csrf token
    #first because login enforces it, and returning the refreshed token afterwards
    def _sign_in(self, username):
        token = self.client.get("/api/auth/csrf/").data["csrfToken"]
        response = self.client.post(
            "/api/auth/login/",
            {"username": username, "password": "synthetic-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        return response, self.client.get("/api/auth/csrf/").data["csrfToken"]

    #method that signs an account in and returns only the response
    def _login(self, username):
        return self._sign_in(username)[0]

    def test_student_with_a_profile_can_sign_in(self):
        response = self._login("example-student")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "example-student")
        self.assertIn("sessionid", self.client.cookies)

    def test_staff_can_still_sign_in(self):
        response = self._login("example-staff-login")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])

    def test_account_without_an_api_role_cannot_sign_in(self):
        response = self._login("example-unlinked")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sessionid", self.client.cookies)

    def test_inactive_account_cannot_sign_in(self):
        self.student_user.is_active = False
        self.student_user.save(update_fields=["is_active"])
        response = self._login("example-student")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sessionid", self.client.cookies)

    def test_every_rejection_returns_the_same_error(self):
        unlinked = self._login("example-unlinked")
        unknown = self.client.post(
            "/api/auth/login/",
            {"username": "no-such-account", "password": "synthetic-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=self.client.get("/api/auth/csrf/").data["csrfToken"],
        )
        wrong = self.client.post(
            "/api/auth/login/",
            {"username": "example-student", "password": "wrong-password"},
            format="json",
            HTTP_X_CSRFTOKEN=self.client.get("/api/auth/csrf/").data["csrfToken"],
        )
        self.assertEqual(unlinked.data, unknown.data)
        self.assertEqual(unlinked.data, wrong.data)

    def test_student_session_reads_its_own_identity(self):
        self._login("example-student")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "example-student")
        self.assertFalse(response.data["is_staff"])
        self.assertNotIn("password", response.data)

    def test_student_session_can_read_its_own_profile(self):
        self._login("example-student")
        response = self.client.get("/api/me/student/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["student_id"], str(self.student.student_id))

    def test_student_session_cannot_read_staff_endpoints(self):
        self._login("example-student")
        self.assertEqual(self.client.get("/api/students/").status_code, 403)

    def test_student_session_can_end_its_own_session(self):
        _, token = self._sign_in("example-student")
        response = self.client.post(
            "/api/auth/logout/", format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)
        self.assertEqual(self.client.get("/api/me/student/").status_code, 403)

    def test_student_logout_without_csrf_token_is_rejected(self):
        #csrf checks are off by default on the test client, so a separate enforcing
        #client is used to prove logout is still protected for a student session
        enforcing = APIClient(enforce_csrf_checks=True)
        token = enforcing.get("/api/auth/csrf/").data["csrfToken"]
        enforcing.post(
            "/api/auth/login/",
            {"username": "example-student", "password": "synthetic-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(enforcing.post("/api/auth/logout/").status_code, 403)
