import io
import smtplib
import socket
import ssl
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings

from .sharing_transport import validate_email_configuration, validate_transport
from .email_backend import EmailBackend
from .email_backend import LoginAuthentication, LoginSMTP, LoginSMTPSSL
from types import SimpleNamespace
from unittest.mock import Mock


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   DEFAULT_FROM_EMAIL="Department <sender@example.test>",
                   RESULT_SHARING_ENABLED=False)
class MockGuardianEmailTests(SimpleTestCase):
    def test_preview_uses_synthetic_data_and_does_not_send_or_access_database(self):
        output = io.StringIO()
        with patch("academics.management.commands.send_mock_guardian_email.submit_email") as send:
            call_command("send_mock_guardian_email", stdout=output)
        send.assert_not_called()
        self.assertIn("TEST ONLY", output.getvalue())
        self.assertIn("Semester GPA: 3.29", output.getvalue())
        self.assertIn("Cumulative CGPA: 2.30", output.getvalue())

    def test_single_mock_submission_does_not_enable_or_drain_bulk_queue(self):
        output = io.StringIO()
        call_command("send_mock_guardian_email", recipient="tester@example.test", send=True, stdout=output)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["tester@example.test"])
        self.assertEqual(mail.outbox[0].cc, [])
        self.assertEqual(mail.outbox[0].bcc, [])
        self.assertIn("FICTIONAL", mail.outbox[0].body)
        self.assertIn("no real email sent", output.getvalue())

    def test_send_requires_one_valid_address(self):
        for recipient in (None, "bad-address", "one@example.test,two@example.test", "one@example.test\nBcc: two@example.test"):
            with self.subTest(recipient=recipient), self.assertRaises(CommandError):
                call_command("send_mock_guardian_email", recipient=recipient, send=True)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_console_output_cannot_claim_a_live_send(self):
        with self.assertRaises(CommandError):
            call_command("send_mock_guardian_email", recipient="tester@example.test", send=True)

    def test_uncertain_outcome_is_not_automatically_retried(self):
        with patch("academics.sharing_transport.EmailMessage.send", side_effect=TimeoutError) as send:
            with self.assertRaisesMessage(CommandError, "uncertain"):
                call_command("send_mock_guardian_email", recipient="tester@example.test", send=True)
        send.assert_called_once()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                   EMAIL_HOST="smtp.gmail.com", EMAIL_HOST_USER="sender@gmail.com",
                   EMAIL_HOST_PASSWORD="synthetic-app-password", EMAIL_PORT=587,
                   EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
                   DEFAULT_FROM_EMAIL="Department <sender@gmail.com>", RESULT_SHARING_ENABLED=True)
class GmailSetupTests(SimpleTestCase):
    @override_settings(EMAIL_BACKEND="academics.email_backend.EmailBackend", EMAIL_SMTP_AUTH_METHOD="LOGIN")
    def test_real_smtp_backend_selects_verified_login_path(self):
        self.assertIs(EmailBackend().connection_class, LoginSMTP)
        self.assertIs(EmailBackend(use_tls=False, use_ssl=True).connection_class, LoginSMTPSSL)
        with patch("academics.email_backend.LoginSMTP") as smtp:
            backend = EmailBackend()
            self.assertTrue(backend.open())
            smtp.return_value.starttls.assert_called_once_with(context=backend.ssl_context)
            smtp.return_value.login.assert_called_once_with("sender@gmail.com", "synthetic-app-password")
            backend.close()

    def test_login_mixin_uses_challenge_response_and_rejects_unadvertised_method(self):
        server = SimpleNamespace(ehlo_or_helo_if_needed=Mock(), esmtp_features={"auth": "PLAIN LOGIN"},
                                 auth=Mock(return_value=(235, b"accepted")), auth_login=Mock())
        self.assertEqual(LoginAuthentication.login(server, "user", "synthetic-secret"), (235, b"accepted"))
        server.auth.assert_called_once_with("LOGIN", server.auth_login, initial_response_ok=False)
        server.esmtp_features = {"auth": "PLAIN"}
        server.auth.reset_mock()
        with self.assertRaises(smtplib.SMTPNotSupportedError):
            LoginAuthentication.login(server, "user", "synthetic-secret")
        server.auth.assert_not_called()

    def test_login_challenge_response_does_not_use_automatic_login_or_send(self):
        output = io.StringIO()
        with patch("academics.management.commands.check_email_connection.smtplib.SMTP") as smtp:
            server = smtp.return_value
            server.ehlo.return_value = (250, b"synthetic")
            server.has_extn.return_value = True
            server.esmtp_features = {"auth": "PLAIN LOGIN"}
            call_command("check_email_connection", auth_method="LOGIN", stdout=output)
        server.auth.assert_called_once_with("LOGIN", server.auth_login, initial_response_ok=False)
        server.login.assert_not_called()
        server.sendmail.assert_not_called()
        self.assertNotIn("synthetic-app-password", output.getvalue())
        self.assertIn("Passed: SMTP authentication", output.getvalue())

    def test_login_method_must_be_advertised(self):
        with patch("academics.management.commands.check_email_connection.smtplib.SMTP") as smtp:
            server = smtp.return_value
            server.ehlo.return_value = (250, b"synthetic")
            server.has_extn.return_value = True
            server.esmtp_features = {"auth": "PLAIN"}
            with self.assertRaisesMessage(CommandError, "LOGIN was not advertised"):
                call_command("check_email_connection", auth_method="LOGIN", stdout=io.StringIO())
        server.auth.assert_not_called()
        server.sendmail.assert_not_called()

    def test_staged_check_reports_handshake_and_login_without_sending(self):
        output = io.StringIO()
        with patch("academics.management.commands.check_email_connection.smtplib.SMTP") as smtp:
            server = smtp.return_value
            server.ehlo.return_value = (250, b"synthetic-private-reply")
            server.has_extn.return_value = True
            call_command("check_email_connection", stages=True, stdout=output)
        self.assertIn("Passed: EHLO after TLS", output.getvalue())
        self.assertIn("Passed: SMTP authentication", output.getvalue())
        self.assertNotIn("synthetic-private-reply", output.getvalue())
        self.assertNotIn("synthetic-app-password", output.getvalue())
        server.login.assert_called_once_with("sender@gmail.com", "synthetic-app-password")
        server.sendmail.assert_not_called()
        server.close.assert_called_once()

    def test_staged_disconnect_identifies_tls_or_authentication_without_leaking(self):
        for method, stage in (("starttls", "TLS handshake"), ("login", "SMTP authentication")):
            with self.subTest(method=method), patch("academics.management.commands.check_email_connection.smtplib.SMTP") as smtp:
                server = smtp.return_value
                server.ehlo.return_value = (250, b"synthetic")
                server.has_extn.return_value = True
                getattr(server, method).side_effect = smtplib.SMTPServerDisconnected("private-server-reply")
                output = io.StringIO()
                with self.assertRaises(CommandError) as caught:
                    call_command("check_email_connection", stages=True, stdout=output)
                self.assertIn("Failed at " + stage, str(caught.exception))
                self.assertNotIn("private-server-reply", str(caught.exception))
                if method == "starttls":
                    server.login.assert_not_called()
                server.sendmail.assert_not_called()
                server.close.assert_called_once()

    @override_settings(EMAIL_BACKEND="academics.email_backend.EmailBackend")
    def test_native_backend_supported_by_setup_and_diagnostic(self):
        validate_email_configuration()
        validate_transport("email")
        with patch("academics.management.commands.check_email_connection.get_connection") as factory:
            factory.return_value.open.return_value = True
            call_command("check_email_connection", stdout=io.StringIO())
        factory.return_value.send_messages.assert_not_called()

    def test_native_context_keeps_hostname_and_certificate_verification(self):
        backend = EmailBackend()
        self.assertTrue(backend.ssl_context.check_hostname)
        self.assertEqual(backend.ssl_context.verify_mode, ssl.CERT_REQUIRED)

    def test_native_context_is_passed_to_starttls_and_failure_prevents_login(self):
        for failure in (None, ssl.SSLCertVerificationError("synthetic failure")):
            with self.subTest(failure=bool(failure)), patch("django.core.mail.backends.smtp.smtplib.SMTP") as smtp:
                smtp.return_value.starttls.side_effect = failure
                backend = EmailBackend()
                if failure:
                    with self.assertRaises(ssl.SSLCertVerificationError):
                        backend.open()
                    smtp.return_value.login.assert_not_called()
                else:
                    self.assertTrue(backend.open())
                    smtp.return_value.login.assert_called_once()
                smtp.return_value.starttls.assert_called_once_with(context=backend.ssl_context)
                smtp.return_value.sendmail.assert_not_called()
                backend.close()

    def test_connection_check_authenticates_but_never_sends(self):
        output = io.StringIO()
        with patch("academics.management.commands.check_email_connection.get_connection") as factory:
            connection = factory.return_value
            connection.open.return_value = True
            call_command("check_email_connection", stdout=output)
        connection.open.assert_called_once()
        connection.close.assert_called_once()
        connection.send_messages.assert_not_called()
        self.assertIn("login succeeded", output.getvalue())
        self.assertIn("No email sent", output.getvalue())

    def test_connection_diagnostics_are_specific_and_never_log_provider_secrets(self):
        errors = [(ssl.SSLCertVerificationError("private-secret"), "certificate verification failed"),
                  (smtplib.SMTPAuthenticationError(535, b"private-secret"), "authentication rejected"),
                  (socket.gaierror("private-secret"), "DNS lookup failed"),
                  (TimeoutError("private-secret"), "timed out"),
                  (ConnectionRefusedError("private-secret"), "connection refused"),
                  (smtplib.SMTPServerDisconnected("private-secret"), "server disconnected")]
        for error, expected in errors:
            with self.subTest(error=type(error).__name__), patch("academics.management.commands.check_email_connection.get_connection") as factory:
                factory.return_value.open.side_effect = error
                with self.assertRaises(CommandError) as caught:
                    call_command("check_email_connection", stdout=io.StringIO())
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("private-secret", str(caught.exception))
                factory.return_value.send_messages.assert_not_called()
                factory.return_value.close.assert_called_once()

    def test_valid_setup_requires_no_network_connection(self):
        with patch("smtplib.SMTP") as smtp:
            validate_email_configuration()
            validate_transport("email")
        smtp.assert_not_called()

    def test_missing_secret_wrong_sender_and_insecure_transport_block_queue(self):
        for values in ({"EMAIL_HOST_PASSWORD": ""}, {"DEFAULT_FROM_EMAIL": "other@gmail.com"},
                       {"EMAIL_USE_TLS": False}, {"EMAIL_USE_SSL": True},
                       {"EMAIL_PORT": 25}, {"EMAIL_HOST": "localhost"},
                       {"DEFAULT_FROM_EMAIL": "noreply@example.invalid"}):
            with self.subTest(values=values), override_settings(**values), self.assertRaises(ValidationError):
                validate_transport("email")

    def test_bad_setup_does_not_attempt_submission_or_reveal_secret(self):
        with override_settings(EMAIL_PORT=25), patch("academics.management.commands.send_mock_guardian_email.submit_email") as send:
            with self.assertRaises(CommandError) as error:
                call_command("send_mock_guardian_email", recipient="tester@example.test", send=True)
        send.assert_not_called()
        self.assertNotIn("synthetic-app-password", str(error.exception))
