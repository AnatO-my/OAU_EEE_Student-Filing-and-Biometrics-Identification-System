"""Security settings, deploy check, and session hardening tests."""
import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from .models import User


class SecuritySettingDefaultsTests(SimpleTestCase):
    #development and the test suite run over plain HTTP, so the transport flags
    #stay off unless DJANGO_SECURE_TRANSPORT is enabled, otherwise every local
    #request would be redirected to an https address that does not exist
    def test_transport_flags_stay_off_without_the_opt_in(self):
        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        self.assertFalse(settings.CSRF_COOKIE_SECURE)
        self.assertFalse(settings.SECURE_SSL_REDIRECT)
        self.assertEqual(settings.SECURE_HSTS_SECONDS, 0)

    def test_response_hardening_is_always_on(self):
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_session_cookie_hardening_defaults(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 12 * 60 * 60)


class DeployCheckTests(SimpleTestCase):
    #runs Django's own deploy check under production-like environment variables
    #and fails the suite if any deployment security warning appears, the only
    #two accepted warnings are HSTS include_subdomains and preload because the
    #deployment domain and its subdomains are not confirmed yet, enabling either
    #before that confirmation is the irreversible mistake
    def test_deploy_check_is_clean_in_production_mode(self):
        repo_root = Path(__file__).resolve().parents[2]
        environment = dict(os.environ)
        environment.update(
            {
                "DJANGO_DEBUG": "false",
                "DJANGO_SECRET_KEY": (
                    "synthetic-deploy-check-only-secret-key-0123456789-abcdef"
                ),
                "DJANGO_SECURE_TRANSPORT": "true",
                "DJANGO_SETTINGS_MODULE": "config.settings",
            }
        )
        result = subprocess.run(
            [sys.executable, "manage.py", "check", "--deploy"],
            cwd=repo_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        accepted = {"security.W005", "security.W021"}
        found = set(re.findall(r"security\.\d*W\d+", output))
        self.assertEqual(
            found,
            accepted,
            "Unexpected deploy warnings:\n" + output,
        )


class SessionKeyRotationTests(TestCase):
    #login must replace the anonymous session key so a session planted before
    #authentication cannot be reused afterwards, this is session fixation
    #protection and it is asserted through the real csrf and login endpoints
    def test_login_rotates_the_anonymous_session_key(self):
        user = User.objects.create_user(
            username="example-staff-fixation",
            password="synthetic-test-password",
            is_staff=True,
        )
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        anonymous_key = client.session.session_key
        response = client.post(
            "/api/auth/login/",
            {"username": user.username, "password": "synthetic-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        authenticated_key = client.session.session_key
        self.assertIsNotNone(anonymous_key)
        self.assertIsNotNone(authenticated_key)
        self.assertNotEqual(anonymous_key, authenticated_key)
