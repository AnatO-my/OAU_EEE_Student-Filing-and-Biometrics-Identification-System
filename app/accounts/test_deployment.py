"""Production failures are caught before deploying or disclosing provider errors."""

import os
import runpy
import sys
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase


class HealthProbeTests(SimpleTestCase):
    def test_liveness_has_no_database_dependency(self):
        with patch("config.health.connection") as connection:
            response = self.client.get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response.headers["Cache-Control"])
        connection.cursor.assert_not_called()

    def test_readiness_checks_database_and_suppresses_failure_details(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        with patch("config.health.connection", connection):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        cursor.execute.assert_called_once_with("SELECT 1")
        connection.cursor.side_effect = OperationalError("private-provider-user-password-host")
        with patch("config.health.connection", connection):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn("private", response.content.decode())

    def test_probes_do_not_accept_writes(self):
        self.assertEqual(self.client.post("/health/live/").status_code, 405)
        self.assertEqual(self.client.post("/health/ready/").status_code, 405)


class ProductionSettingsTests(SimpleTestCase):
    environment = {
        "POSTGRES_HOST": "synthetic.aivencloud.com",
        "POSTGRES_DB": "synthetic_deployment",
        "POSTGRES_USER": "synthetic_user",
        "POSTGRES_PASSWORD": "synthetic-password",
        "DJANGO_SECRET_KEY": "synthetic-key-for-isolated-configuration-checks-0123456789abcdef",
        "DJANGO_ALLOWED_HOSTS": "portal.example.invalid,localhost",
    }

    def load(self, **overrides):
        # Import environment-dependent settings afresh without changing the
        # actual test runner's configured settings or making any connection.
        with patch.dict(os.environ, {**self.environment, **overrides}, clear=True), patch.dict(sys.modules):
            sys.modules.pop("config.settings", None)
            sys.modules.pop("config.postgres_settings", None)
            return runpy.run_module("config.production_settings")

    def test_secure_defaults_and_proxy_trust_are_explicit(self):
        settings = self.load()
        self.assertFalse(settings["DEBUG"])
        self.assertTrue(settings["SECURE_SSL_REDIRECT"])
        self.assertTrue(settings["SESSION_COOKIE_SECURE"])
        self.assertTrue(settings["CSRF_COOKIE_SECURE"])
        self.assertIsNone(settings["SECURE_PROXY_SSL_HEADER"])
        self.assertEqual(settings["STATIC_URL"], "/static/")
        settings = self.load(DJANGO_TRUST_PROXY_HEADERS="true")
        self.assertEqual(settings["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_bad_secret_hosts_database_tls_and_reset_url_fail_closed(self):
        for overrides, message in (
            ({"DJANGO_SECRET_KEY": "short"}, "stable random"),
            ({"DJANGO_ALLOWED_HOSTS": ""}, "explicit deployment hostnames"),
            ({"DJANGO_ALLOWED_HOSTS": "*"}, "without wildcards"),
            ({"POSTGRES_SSLMODE": "require"}, "verify-full"),
            ({"DJANGO_CSRF_TRUSTED_ORIGINS": "http://portal.example.invalid"}, "HTTPS origins"),
            ({"PASSWORD_RESET_FRONTEND_URL": "http://portal.example.invalid/reset-password"}, "must use HTTPS"),
            ({"DJANGO_EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend"}, "real email backend"),
        ):
            with self.subTest(overrides=overrides), self.assertRaisesMessage(ImproperlyConfigured, message):
                self.load(**overrides)
