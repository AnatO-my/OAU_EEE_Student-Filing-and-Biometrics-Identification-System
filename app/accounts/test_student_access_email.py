"""Exact matric login names and reviewed email access without real SMTP traffic."""
from io import StringIO
import json
from contextlib import redirect_stdout
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from students.models import Student
from .models import AccountAdministrationAudit, User
from .student_access_email import email_configuration_status, send_student_access_email
from .student_setup import confirm_student_setup, student_setup_tokens
from .test_student_setup import StudentSetupFixture


SMTP_CONFIGURATION = {
    "EMAIL_BACKEND": "academics.email_backend.EmailBackend", "EMAIL_HOST": "smtp.example.test",
    "EMAIL_PORT": 587, "EMAIL_USE_TLS": True, "EMAIL_USE_SSL": False,
    "EMAIL_HOST_USER": "sender@example.test", "EMAIL_HOST_PASSWORD": "synthetic-smtp-secret",
    "DEFAULT_FROM_EMAIL": "sender@example.test", "STUDENT_ACCOUNT_FRONTEND_ORIGIN": "https://portal.example.test",
}


@override_settings(**SMTP_CONFIGURATION)
class StudentAccessEmailTests(StudentSetupFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.email_url = f"/api/students/{self.student.pk}/account/email-link/"

    def review(self, issued, **changes):
        return {"expected_username": issued["account"]["username"], "expected_email": issued["account"]["email"],
            "confirm_reissue": True, **changes}

    def test_new_setup_defaults_to_exact_matric_and_sign_in_preserves_slashes_and_zeros(self):
        self.student.identifier_value = "TEST/2026/0001"
        self.student.save(update_fields=["identifier_value"])
        response = self.client.post(self.issue_url, {"email": "student@example.test"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["account"]["username"], "TEST/2026/0001")
        confirm_student_setup(**self.confirm_body(response.data))
        public = APIClient()
        logged_in = public.post("/api/auth/login/", {"username": "TEST/2026/0001", "password": self.password}, format="json")
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(logged_in.data["username"], "TEST/2026/0001")
        self.assertEqual(public.get("/api/me/student/").data["student_id"], str(self.student.pk))

    def test_model_and_django_admin_username_field_accept_slashes_but_reject_spaces(self):
        username_field = User._meta.get_field("username")
        username_field.clean("TEST/2026/0001", None)
        username_field.clean("Unicode-É/0001@.+_", None)
        with self.assertRaises(ValidationError):
            username_field.clean("TEST 2026/0001", None)
        request = RequestFactory().get("/admin/accounts/user/add/")
        request.user = self.hod
        form_class = admin.site._registry[User].get_form(request)
        self.assertEqual(form_class.base_fields["username"].clean("TEST/2026/0001"), "TEST/2026/0001")

    def test_identifier_requiring_unicode_normalization_is_not_silently_changed(self):
        self.student.identifier_value = "ＴＥＳＴ/2026/0001"
        self.student.save(update_fields=["identifier_value"])
        response = self.client.post(self.issue_url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.user_id)

    def test_pending_rename_rejects_unicode_normalization_without_changing_email_or_token(self):
        issued = self.issue()
        self.student.identifier_value = "ＴＥＳＴ/２０２６/００１"
        self.student.save(update_fields=["identifier_value"])
        response = self.client.patch(self.account_url, {"expected_username": issued["account"]["username"],
            "expected_email": issued["account"]["email"], "email": "must-not-change@example.test",
            "use_student_identifier": True, "expected_identifier_value": self.student.identifier_value}, format="json")
        self.assertEqual(response.status_code, 400)
        account = User.objects.get(pk=issued["account"]["id"])
        self.assertEqual(account.username, issued["account"]["username"])
        self.assertEqual(account.email, issued["account"]["email"])
        self.assertTrue(student_setup_tokens.check_token(account, issued["token"]))

    def test_metadata_has_preferred_username_and_safe_email_configuration_status(self):
        response = self.client.get(self.account_url)
        self.assertEqual(response.data["preferred_username"], self.student.identifier_value)
        self.assertTrue(response.data["email_delivery_available"])
        encoded = json.dumps(response.data)
        for secret in (settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD, settings.EMAIL_HOST):
            self.assertNotIn(secret, encoded)

    def test_usable_account_rename_is_explicit_and_preserves_password_id_student_link_and_session(self):
        issued = self.issue()
        account = confirm_student_setup(**self.confirm_body(issued))
        original_password = account.password
        student_client = APIClient()
        student_client.force_login(account)
        before = self.client.get(self.account_url)
        self.assertEqual(before.data["account"]["username"], "setup-student")
        response = self.client.patch(self.account_url, {"expected_username": account.username,
            "expected_email": account.email, "email": "reviewed@example.test", "use_student_identifier": True,
            "expected_identifier_value": self.student.identifier_value}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        account.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(account.pk, issued["account"]["id"])
        self.assertEqual(account.username, self.student.identifier_value)
        self.assertEqual(account.email, "reviewed@example.test")
        self.assertEqual(account.password, original_password)
        self.assertEqual(self.student.user_id, account.pk)
        self.assertEqual(student_client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(student_client.get("/api/auth/me/").data["username"], self.student.identifier_value)
        self.assertEqual(student_client.get("/api/me/student/").data["student_id"], str(self.student.pk))

    def test_pending_rename_or_email_update_revokes_previously_issued_setup_link(self):
        issued = self.issue()
        response = self.client.patch(self.account_url, {"expected_username": issued["account"]["username"],
            "expected_email": issued["account"]["email"], "email": "reviewed@example.test",
            "use_student_identifier": True, "expected_identifier_value": self.student.identifier_value}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        account = User.objects.get(pk=issued["account"]["id"])
        self.assertFalse(account.has_usable_password())
        self.assertFalse(student_setup_tokens.check_token(account, issued["token"]))

    def test_stale_review_or_username_collision_rolls_back_username_and_email(self):
        issued = self.issue()
        collision = User.objects.create_user(self.student.identifier_value, password=self.password)
        body = {"expected_username": issued["account"]["username"], "expected_email": issued["account"]["email"],
            "email": "must-not-change@example.test", "use_student_identifier": True,
            "expected_identifier_value": self.student.identifier_value}
        for changes in ({}, {"expected_username": "stale"}, {"expected_email": "stale@example.test"},
                {"expected_identifier_value": "STALE/0001"}):
            response = self.client.patch(self.account_url, {**body, **changes}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            account = User.objects.get(pk=issued["account"]["id"])
            self.assertEqual(account.username, issued["account"]["username"])
            self.assertEqual(account.email, issued["account"]["email"])
            self.assertTrue(student_setup_tokens.check_token(account, issued["token"]))
        self.assertEqual(User.objects.filter(username=collision.username).count(), 1)
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="student_login_updated").count(), 0)

    def test_setup_email_contains_username_and_private_fragment_link_not_password_or_raw_response_token(self):
        issued = self.issue()
        messages = []

        def capture(message, **kwargs):
            messages.append(message)
            return 1

        with patch("accounts.student_access_email.EmailMessage.send", autospec=True, side_effect=capture) as sender:
            response = self.client.post(self.email_url, self.review(issued), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["kind"], "setup")
        self.assertEqual(response.data["delivery_status"], "accepted")
        self.assertEqual(response.data["recipient"], issued["account"]["email"])
        self.assertEqual(sender.call_count, 1)
        message, = messages
        self.assertEqual(message.to, [issued["account"]["email"]])
        self.assertIn(issued["account"]["username"], message.body)
        self.assertNotIn(self.password, message.body)
        self.assertNotIn("laptop running", message.body)
        link, = [line for line in message.body.splitlines() if line.startswith("https://")]
        url = urlsplit(link)
        self.assertEqual((url.scheme, url.netloc, url.path, url.query), ("https", "portal.example.test", "/setup-student", ""))
        payload = {key: values[0] for key, values in parse_qs(url.fragment).items()}
        account = User.objects.get(pk=issued["account"]["id"])
        self.assertFalse(student_setup_tokens.check_token(account, issued["token"]))
        self.assertTrue(student_setup_tokens.check_token(account, payload["token"]))
        self.assertNotIn(payload["token"], json.dumps(response.data))
        event = AccountAdministrationAudit.objects.get(action="student_access_email_issued")
        self.assertNotIn(payload["token"], json.dumps(event.after))

    def test_usable_account_email_contains_reset_link_and_does_not_change_password(self):
        issued = self.issue()
        account = confirm_student_setup(**self.confirm_body(issued))
        old_hash = account.password
        messages = []
        with patch("accounts.student_access_email.EmailMessage.send", autospec=True,
                side_effect=lambda message, **kwargs: messages.append(message) or 1):
            response = self.client.post(self.email_url, self.review(issued), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["kind"], "reset")
        account.refresh_from_db()
        self.assertEqual(account.password, old_hash)
        link, = [line for line in messages[0].body.splitlines() if line.startswith("https://")]
        parsed = urlsplit(link)
        self.assertEqual(parsed.path, "/reset-password")
        payload = {key: values[0] for key, values in parse_qs(parsed.fragment).items()}
        self.assertTrue(default_token_generator.check_token(account, payload["token"]))
        self.assertEqual(User.objects.count(), 3)

    def test_email_unknown_outcome_suppresses_provider_errors_and_never_retries(self):
        issued = self.issue()
        with patch("accounts.student_access_email.EmailMessage.send", side_effect=OSError("raw-provider-private-secret")) as sender:
            response = self.client.post(self.email_url, self.review(issued), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["delivery_status"], "unknown")
        self.assertNotIn("raw-provider", json.dumps(response.data))
        self.assertNotIn("token", response.data)
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="student_access_email_issued").count(), 1)

    def test_configuration_failure_prevents_token_rotation_and_console_output(self):
        issued = self.issue()
        for backend in ("django.core.mail.backends.console.EmailBackend", "django.core.mail.backends.dummy.EmailBackend",
                "django.core.mail.backends.filebased.EmailBackend", "django.core.mail.backends.locmem.EmailBackend"):
            with self.subTest(backend=backend), override_settings(EMAIL_BACKEND=backend), patch("accounts.student_access_email.EmailMessage.send") as sender:
                output = StringIO()
                with redirect_stdout(output):
                    response = self.client.post(self.email_url, self.review(issued), format="json")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.data["code"], "student_email_not_configured")
                sender.assert_not_called()
                self.assertEqual(output.getvalue(), "")
                account = User.objects.get(pk=issued["account"]["id"])
                self.assertTrue(student_setup_tokens.check_token(account, issued["token"]))
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="student_access_email_issued").count(), 0)

    def test_missing_tls_gmail_auth_and_untrusted_http_origins_disable_email_before_changes(self):
        issued = self.issue()
        invalid = [
            {"EMAIL_USE_TLS": False, "EMAIL_USE_SSL": False},
            {"EMAIL_HOST": "smtp.gmail.com", "EMAIL_HOST_PASSWORD": ""},
            {"STUDENT_ACCOUNT_FRONTEND_ORIGIN": "http://portal.example.test"},
            {"STUDENT_ACCOUNT_FRONTEND_ORIGIN": "https://portal.example.test/path"},
            {"STUDENT_ACCOUNT_FRONTEND_ORIGIN": "https://user:password@portal.example.test"},
            {"STUDENT_ACCOUNT_FRONTEND_ORIGIN": "http://127.0.0.1:5175", "DEBUG": False},
        ]
        for options in invalid:
            with self.subTest(options=list(options)), override_settings(**options), patch("accounts.student_access_email.EmailMessage.send") as sender:
                response = self.client.post(self.email_url, self.review(issued), format="json")
                self.assertEqual(response.status_code, 503, response.data)
                self.assertEqual(response.data["code"], "student_email_not_configured")
                self.assertFalse(email_configuration_status()["email_delivery_available"])
                sender.assert_not_called()
                account = User.objects.get(pk=issued["account"]["id"])
                self.assertTrue(student_setup_tokens.check_token(account, issued["token"]))
        with override_settings(DEBUG=True, STUDENT_ACCOUNT_FRONTEND_ORIGIN="http://127.0.0.1:5175"):
            self.assertTrue(email_configuration_status()["email_delivery_available"])

    @override_settings(DEBUG=True, STUDENT_ACCOUNT_FRONTEND_ORIGIN="http://127.0.0.1:5175")
    def test_local_email_explains_that_recipient_must_open_link_on_portal_laptop(self):
        issued = self.issue()
        messages = []
        with patch("accounts.student_access_email.EmailMessage.send", autospec=True,
                side_effect=lambda message, **kwargs: messages.append(message) or 1):
            response = self.client.post(self.email_url, self.review(issued), format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Open this link on the laptop running the department portal", messages[0].body)

    def test_stale_recipient_blank_email_missing_confirmation_and_nonhod_are_rejected_without_send(self):
        issued = self.issue()
        for changes in ({"expected_username": "stale"}, {"expected_email": "stale@example.test"},
                {"confirm_reissue": False}):
            with patch("accounts.student_access_email.EmailMessage.send") as sender:
                response = self.client.post(self.email_url, self.review(issued, **changes), format="json")
                self.assertEqual(response.status_code, 400)
                sender.assert_not_called()
        account = User.objects.get(pk=issued["account"]["id"])
        account.email = ""
        account.save(update_fields=["email"])
        with patch("accounts.student_access_email.EmailMessage.send") as sender:
            response = self.client.post(self.email_url, self.review(issued, expected_email=""), format="json")
            self.assertEqual(response.status_code, 400)
            sender.assert_not_called()
            client = APIClient()
            client.force_authenticate(self.staff)
            self.assertEqual(client.post(self.email_url, self.review(issued), format="json").status_code, 403)
            self.assertEqual(client.patch(self.account_url, {"expected_username": account.username,
                "expected_email": "", "email": "untrusted@example.test"}, format="json").status_code, 403)

    def test_contact_patch_and_email_action_require_session_csrf(self):
        issued = self.issue()
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.hod)
        self.assertEqual(client.patch(self.account_url, {"expected_username": issued["account"]["username"],
            "expected_email": issued["account"]["email"], "email": "new@example.test"}, format="json").status_code, 403)
        with patch("accounts.student_access_email.EmailMessage.send") as sender:
            self.assertEqual(client.post(self.email_url, self.review(issued), format="json").status_code, 403)
            sender.assert_not_called()


@override_settings(**SMTP_CONFIGURATION)
class StudentAccessEmailTransactionTests(StudentSetupFixture, TransactionTestCase):
    def test_smtp_submission_occurs_only_after_preparation_transaction_releases_locks(self):
        issued = self.issue()
        called = []

        def submit(message, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            self.assertTrue(AccountAdministrationAudit.objects.filter(action="student_access_email_issued").exists())
            called.append(message.to)
            return 1

        with patch("accounts.student_access_email.EmailMessage.send", autospec=True, side_effect=submit):
            response = send_student_access_email(actor=self.hod, student_id=self.student.pk,
                expected_username=issued["account"]["username"], expected_email=issued["account"]["email"], confirm_reissue=True)
        self.assertEqual(response["delivery_status"], "accepted")
        self.assertEqual(called, [[issued["account"]["email"]]])
