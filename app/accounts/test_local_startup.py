"""Local link routing must match the launcher's port without enabling delivery."""
import importlib.util
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase


module_spec = importlib.util.spec_from_file_location(
    "student_account_local_launcher", Path(__file__).resolve().parents[2] / "scripts" / "run_local.py")
local_launcher = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(local_launcher)


class StudentEmailLocalStartupTests(SimpleTestCase):
    def environment(self, certificate, **changes):
        return {
            "DJANGO_SETTINGS_MODULE": "config.postgres_settings", "POSTGRES_HOST": "db.example.test",
            "POSTGRES_PORT": "14172", "POSTGRES_DB": "synthetic", "POSTGRES_USER": "synthetic",
            "POSTGRES_PASSWORD": "synthetic-not-a-real-password", "POSTGRES_SSLMODE": "verify-full",
            "POSTGRES_SSLROOTCERT": certificate, **changes,
        }

    def test_loopback_email_origin_tracks_selected_port_and_console_does_not_enable_recovery(self):
        with tempfile.NamedTemporaryFile() as certificate, patch.dict(os.environ,
                self.environment(certificate.name, DJANGO_EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
                    STUDENT_ACCOUNT_FRONTEND_ORIGIN="https://old.example.test"), clear=True):
            environment = local_launcher.local_environment(8002, 5177)
        self.assertEqual(environment["STUDENT_ACCOUNT_FRONTEND_ORIGIN"], "http://127.0.0.1:5177")
        self.assertNotIn("PASSWORD_RESET_FRONTEND_URL", environment)
        self.assertNotIn("RESULT_SHARING_ENABLED", environment)

    def test_smtp_configuration_enables_local_recovery_page_without_enabling_worker(self):
        with tempfile.NamedTemporaryFile() as certificate, patch.dict(os.environ,
                self.environment(certificate.name, DJANGO_EMAIL_BACKEND="academics.email_backend.EmailBackend",
                    DJANGO_EMAIL_HOST="smtp.example.test", DJANGO_EMAIL_HOST_USER="sender@example.test",
                    DJANGO_EMAIL_HOST_PASSWORD="synthetic-smtp-secret"), clear=True):
            environment = local_launcher.local_environment(8002, 5177)
        self.assertEqual(environment["PASSWORD_RESET_FRONTEND_URL"], "http://127.0.0.1:5177/reset-password")
        self.assertNotIn("RESULT_SHARING_ENABLED", environment)

    def test_explicit_recovery_url_is_preserved_and_incomplete_smtp_cannot_enable_it(self):
        with tempfile.NamedTemporaryFile() as certificate:
            smtp_environment = self.environment(certificate.name,
                DJANGO_EMAIL_BACKEND="academics.email_backend.EmailBackend", DJANGO_EMAIL_HOST="smtp.example.test",
                DJANGO_EMAIL_HOST_USER="sender@example.test", DJANGO_EMAIL_HOST_PASSWORD="synthetic-smtp-secret",
                PASSWORD_RESET_FRONTEND_URL="https://explicit.example.test/reset-password")
            with patch.dict(os.environ, smtp_environment, clear=True):
                self.assertEqual(local_launcher.local_environment()["PASSWORD_RESET_FRONTEND_URL"],
                    "https://explicit.example.test/reset-password")
            smtp_environment.pop("PASSWORD_RESET_FRONTEND_URL")
            smtp_environment.pop("DJANGO_EMAIL_HOST_PASSWORD")
            with patch.dict(os.environ, smtp_environment, clear=True):
                self.assertNotIn("PASSWORD_RESET_FRONTEND_URL", local_launcher.local_environment())
