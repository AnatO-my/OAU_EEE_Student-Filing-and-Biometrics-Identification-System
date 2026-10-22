"""Hosted database setup must preserve TLS and avoid exposing connection secrets."""

import io
import os
import runpy
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.db import OperationalError
from django.test import SimpleTestCase


class PostgresSettingsTests(SimpleTestCase):
    environment = {
        "POSTGRES_DB": "synthetic_integration",
        "POSTGRES_USER": "synthetic_user",
        "POSTGRES_PASSWORD": " synthetic-secret ",
        "POSTGRES_HOST": "synthetic.aivencloud.com",
        "POSTGRES_PORT": "21543",
    }

    def load_database(self, **overrides):
        with patch.dict(os.environ, {**self.environment, **overrides}, clear=True):
            return runpy.run_module("config.postgres_settings")["DATABASES"]["default"]

    def test_hosted_defaults_verify_hostname_and_bound_connection_time(self):
        database = self.load_database()
        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["PORT"], "21543")
        self.assertEqual(database["PASSWORD"], " synthetic-secret ")
        self.assertEqual(database["OPTIONS"], {"sslmode": "verify-full", "connect_timeout": 10})
        self.assertEqual(database["CONN_MAX_AGE"], 0)

    def test_service_certificate_and_timeout_are_forwarded(self):
        database = self.load_database(POSTGRES_SSLROOTCERT="C:/private data/ca.pem", POSTGRES_CONNECT_TIMEOUT="15")
        self.assertEqual(database["OPTIONS"]["sslrootcert"], "C:/private data/ca.pem")
        self.assertEqual(database["OPTIONS"]["connect_timeout"], 15)
        self.assertEqual(database["OPTIONS"]["sslmode"], "verify-full")

    def test_unset_certificate_does_not_override_libpq_environment(self):
        database = self.load_database(PGSSLROOTCERT="C:/private data/ca.pem", POSTGRES_SSLROOTCERT=" ")
        self.assertNotIn("sslrootcert", database["OPTIONS"])

    def test_invalid_timeouts_fail_before_connecting(self):
        for timeout in ("0", "-1", "invalid", ""):
            with self.subTest(timeout=timeout), self.assertRaisesMessage(ImproperlyConfigured, "positive integer"):
                self.load_database(POSTGRES_CONNECT_TIMEOUT=timeout)

    def test_missing_host_does_not_fall_back_to_a_local_or_legacy_database(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "Set POSTGRES_HOST"):
            self.load_database(POSTGRES_HOST="")


class DatabaseConnectionCommandTests(SimpleTestCase):
    def database(self, *, tls=True):
        connection = MagicMock()
        connection.vendor = "postgresql"
        connection.settings_dict = {"OPTIONS": {"sslmode": "verify-full"}}
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            "16.10", 20, 8 * 1024 * 1024, tls, False,
        )
        return connection

    def run_check(self, connection, output):
        with patch("accounts.management.commands.check_database_connection.connections", {"default": connection}):
            call_command("check_database_connection", stdout=output)

    def test_success_reports_tls_and_capacity_without_writes(self):
        connection = self.database()
        output = io.StringIO()
        self.run_check(connection, output)
        self.assertIn("TLS active: yes", output.getvalue())
        self.assertIn("connection limit: 20", output.getvalue())
        self.assertIn("migration table present: no", output.getvalue())
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once()
        self.assertTrue(cursor.execute.call_args.args[0].startswith("SELECT "))
        connection.ensure_connection.assert_called_once()
        connection.close.assert_called_once()

    def test_sqlite_is_rejected_before_any_database_query(self):
        connection = self.database()
        connection.vendor = "sqlite"
        with self.assertRaisesMessage(CommandError, "config.postgres_settings"):
            self.run_check(connection, io.StringIO())
        connection.cursor.assert_not_called()

    def test_required_tls_cannot_report_success_without_encryption(self):
        connection = self.database(tls=False)
        output = io.StringIO()
        with self.assertRaisesMessage(CommandError, "did not report TLS"):
            self.run_check(connection, output)
        self.assertNotIn("check passed", output.getvalue())
        connection.close.assert_called_once()

    def test_provider_errors_never_disclose_password_or_connection_string(self):
        connection = self.database()
        connection.cursor.side_effect = OperationalError("postgresql://private-user:private-password@private-host/db")
        output = io.StringIO()
        with self.assertRaises(CommandError) as caught:
            self.run_check(connection, output)
        rendered = str(caught.exception) + output.getvalue()
        self.assertIn("credentials were suppressed", rendered)
        for secret in ("private-user", "private-password", "private-host"):
            self.assertNotIn(secret, rendered)
        connection.close.assert_called_once()

    def test_authentication_failure_has_a_safe_actionable_message(self):
        connection = self.database()
        error = OperationalError("private-provider-message")
        error.__cause__ = Exception("private-password")
        error.__cause__.sqlstate = "28P01"
        connection.ensure_connection.side_effect = error
        with self.assertRaisesMessage(CommandError, "Authentication rejected") as caught:
            self.run_check(connection, io.StringIO())
        self.assertNotIn("private-", str(caught.exception))

    def test_connection_failures_without_sqlstate_are_classified_without_disclosure(self):
        cases = (
            ("certificate contains IP address with invalid length 16", "IP-address entry"),
            ("fe_sendauth: no password supplied", "No database password"),
            ('password authentication failed for user "private-user"', "Authentication rejected"),
            ("could not translate host name private-host", "DNS lookup failed"),
            ("root certificate file private-path does not exist", "TLS certificate verification failed"),
            ("certificate verify failed", "TLS certificate verification failed"),
            ("connection timeout expired", "Connection timed out"),
            ("connection refused", "TCP connection was refused"),
            ("server closed the connection unexpectedly", "remote connection was closed"),
        )
        for provider_message, expected in cases:
            with self.subTest(category=expected):
                connection = self.database()
                connection.ensure_connection.side_effect = OperationalError(provider_message + " private-secret")
                output = io.StringIO()
                with self.assertRaisesMessage(CommandError, expected) as caught:
                    self.run_check(connection, output)
                rendered = str(caught.exception) + output.getvalue()
                self.assertNotIn("private-", rendered)
                self.assertNotIn("Passed:", rendered)
                connection.cursor.assert_not_called()
                connection.close.assert_called_once()

    def test_query_failure_reports_that_login_succeeded(self):
        connection = self.database()
        error = OperationalError("private-provider-message")
        error.__cause__ = Exception("private-user")
        error.__cause__.pgcode = "42501"
        connection.cursor.side_effect = error
        output = io.StringIO()
        with self.assertRaisesMessage(CommandError, "read-only database diagnostics") as caught:
            self.run_check(connection, output)
        self.assertIn("Passed: connection, TLS and authentication", output.getvalue())
        self.assertIn("lacks permission", str(caught.exception))
        self.assertNotIn("private-", str(caught.exception))
