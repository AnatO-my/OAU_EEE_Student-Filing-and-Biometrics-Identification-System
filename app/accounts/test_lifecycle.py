import re
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import Permission
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient

from .models import User, AdviserAssignment
from students.models import Student


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   PASSWORD_RESET_FRONTEND_URL="https://frontend.example.test/reset-password",
                   CURRENT_ACADEMIC_SESSION="2026/2027")
class AccountLifecycleTests(APITestCase):
    old_password = "Original!8302-Cedar"
    new_password = "Replacement!9104-Coral"

    def setUp(self):
        cache.clear()
        self.hod = User.objects.create_superuser("lifecycle-hod", "hod@example.test", self.old_password)
        self.staff = User.objects.create_user("lifecycle-staff", email="staff@example.test", password=self.old_password, is_staff=True)
        self.student = Student.objects.create(identifier_type="matriculation", identifier_value="000123",
            full_name="Example Student", phone_number="08000000000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        self.account = User.objects.create_user("lifecycle-student", email="student@example.test", password=self.old_password)
        self.student.user = self.account
        self.student.save(update_fields=["user"])

    def reset_payload(self):
        response = self.client.post(reverse("password-reset"), {"email": self.account.email}, format="json")
        self.assertEqual(response.status_code, 200)
        link = re.search(r"https://[^\s]+", mail.outbox[-1].body).group()
        query = parse_qs(urlsplit(link).query)
        return {"uid": query["uid"][0], "token": query["token"][0], "new_password": self.new_password}

    def test_current_password_is_required_and_password_strength_enforced(self):
        self.client.force_authenticate(self.account)
        url = reverse("password-change")
        for old, new in (("wrong", self.new_password), (self.old_password, "123")):
            self.assertEqual(self.client.post(url, {"current_password": old, "new_password": new}, format="json").status_code, 400)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(self.old_password))

    def test_password_change_preserves_current_session_and_revokes_other_session(self):
        first, second = APIClient(), APIClient()
        first.force_login(self.account)
        second.force_login(self.account)
        response = first.post(reverse("password-change"),
            {"current_password": self.old_password, "new_password": self.new_password}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(first.get(reverse("auth-me")).status_code, 200)
        self.assertEqual(second.get(reverse("auth-me")).status_code, 403)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(self.new_password))

    def test_reset_request_has_same_response_for_known_and_unknown_email(self):
        known = self.client.post(reverse("password-reset"), {"email": self.account.email}, format="json")
        unknown = self.client.post(reverse("password-reset"), {"email": "unknown@example.test"}, format="json")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("token", known.data)

    def test_reset_link_is_single_use(self):
        payload = self.reset_payload()
        url = reverse("password-reset-confirm")
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(self.new_password))

    def test_reset_expiry_is_enforced(self):
        payload = self.reset_payload()
        with patch.object(default_token_generator, "_now", return_value=datetime.now() + timedelta(hours=2)):
            self.assertEqual(self.client.post(reverse("password-reset-confirm"), payload, format="json").status_code, 400)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(self.old_password))

    def test_invalid_link_and_weak_password_fail(self):
        url = reverse("password-reset-confirm")
        self.assertEqual(self.client.post(url, {"uid": "%%%", "token": "bad", "new_password": self.new_password}, format="json").status_code, 400)
        payload = self.reset_payload()
        payload["new_password"] = "123"
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)

    @override_settings(PASSWORD_RESET_FRONTEND_URL="")
    def test_unconfigured_recovery_fails_without_account_disclosure(self):
        for email in (self.account.email, "unknown@example.test"):
            self.assertEqual(self.client.post(reverse("password-reset"), {"email": email}, format="json").status_code, 503)

    def test_reset_endpoints_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("password-reset"), {"email": self.account.email}, format="json").status_code, 403)
        self.assertEqual(client.post(reverse("password-reset-confirm"), {}, format="json").status_code, 403)
        token = client.get(reverse("auth-csrf")).data["csrfToken"]
        response = client.post(reverse("password-reset"), {"email": self.account.email}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_hod_provisioning_never_grants_privileges_or_returns_password(self):
        other = Student.objects.create(identifier_type="matriculation", identifier_value="000124",
            full_name="New student", phone_number="08000000000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        self.client.force_authenticate(self.hod)
        url = reverse("student-account", kwargs={"student_id": other.pk})
        response = self.client.post(url, {"username": "new-student", "email": "new@example.test",
            "password": self.new_password, "is_staff": True, "is_superuser": True}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        other.refresh_from_db()
        self.assertFalse(other.user.is_staff)
        self.assertFalse(other.user.is_superuser)
        self.assertTrue(other.user.check_password(self.new_password))
        self.assertEqual(self.client.post(url, {"username": "duplicate-student", "email": "new@example.test",
            "password": self.new_password}, format="json").status_code, 400)
        self.assertFalse(User.objects.filter(username="duplicate-student").exists())

    def test_linking_rejects_staff_and_already_linked_accounts(self):
        other = Student.objects.create(identifier_type="matriculation", identifier_value="000124",
            full_name="New student", phone_number="08000000000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        self.client.force_authenticate(self.hod)
        url = reverse("student-account", kwargs={"student_id": other.pk})
        for account in (self.hod, self.staff, self.account):
            self.assertEqual(self.client.put(url, {"account_id": account.pk}, format="json").status_code, 400)
        unlinked = User.objects.create_user("unlinked-student", password=self.new_password)
        self.assertEqual(self.client.put(url, {"account_id": unlinked.pk}, format="json").status_code, 200)
        other.refresh_from_db()
        self.assertEqual(other.user_id, unlinked.pk)

    def test_staff_cannot_provision_or_link_student_account(self):
        self.client.force_authenticate(self.staff)
        url = reverse("student-account", kwargs={"student_id": self.student.pk})
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 403)
        self.assertEqual(self.client.put(url, {"account_id": self.account.pk}, format="json").status_code, 403)

    def test_current_user_reports_permissions_and_assignment_levels(self):
        permission = Permission.objects.get(content_type__app_label="students", codename="view_student")
        self.staff.user_permissions.add(permission)
        AdviserAssignment.objects.create(staff=self.staff, academic_session="2026/2027", level=300)
        self.staff = User.objects.get(pk=self.staff.pk)
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "staff")
        self.assertIn("students.view_student", response.data["permissions"])
        self.assertEqual(response.data["adviser_levels"], [300])

    @override_settings(REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
        "DEFAULT_THROTTLE_RATES": {"password_reset": "1/hour", "password_reset_confirm": "60/hour"},
    })
    def test_password_reset_is_rate_limited(self):
        url = reverse("password-reset")
        self.assertEqual(self.client.post(url, {"email": "unknown@example.test"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {"email": "unknown@example.test"}, format="json").status_code, 429)
