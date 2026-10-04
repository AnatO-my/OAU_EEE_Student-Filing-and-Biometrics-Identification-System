from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


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

    def test_logout_without_csrf_token_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 403)

    def test_student_reads_without_csrf_token_still_succeed(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)

    def test_login_succeeds_without_a_prior_csrf_token(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "example-staff", "password": "synthetic-test-password"},
            format="json",
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
