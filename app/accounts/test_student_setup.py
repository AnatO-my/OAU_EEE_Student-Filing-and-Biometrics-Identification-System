"""Synthetic first-login setup, privilege boundaries and concurrency coverage."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from threading import Barrier, Event
import time
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from students.models import Student
from .administration import locked_users, transfer_hod
from .lifecycle import link_student_account, provision_student_account
from .models import AccountAdministrationAudit, User
from .student_setup import confirm_student_setup, issue_student_setup, student_setup_tokens


def complete_accepted_handover(*, actor, target_staff_id, **unused_legacy_confirmation):
    """Exercise the accepted lifecycle where old tests need a completed transfer."""
    from django.db import transaction
    from accounts import administration
    from accounts.batch_services import offer_handover, accept_handover
    with transaction.atomic():
        administration.locked_users(actor, target_staff_id)
        offered = offer_handover(actor=actor, target_id=target_staff_id)
        return accept_handover(actor=User.objects.get(pk=target_staff_id), handover_id=offered.pk)



class StudentSetupFixture:
    password = "Synthetic!Student-7295-Cedar"

    def setUp(self):
        super().setUp()
        cache.clear()
        self.hod = User.objects.create_superuser("setup-hod", "hod@example.test", self.password)
        self.staff = User.objects.create_user("setup-staff", password=self.password, is_staff=True)
        self.student = Student.objects.create(identifier_type="matriculation", identifier_value="SYNTHETIC/SETUP/001",
            full_name="Synthetic Setup Student", phone_number="", admission_year=2026,
            mode_of_admission="utme", current_level=100)
        self.client = APIClient()
        self.client.force_authenticate(self.hod)
        self.issue_url = f"/api/students/{self.student.pk}/account/setup-link/"
        self.account_url = f"/api/students/{self.student.pk}/account/"
        self.confirm_url = "/api/auth/student/setup/confirm/"

    def seed_legacy_account(self, **values):
        self.student.refresh_from_db()
        if self.student.user_id is None:
            account = User(username=values.get("username", "setup-student"), email=values.get("email", "student@example.test"), is_active=True)
            account.set_unusable_password()
            account.full_clean()
            account.save()
            self.student.user=account
            self.student.save(update_fields=["user"])
        return self.student.user

    def issue(self, **values):
        self.seed_legacy_account(**values)
        return issue_student_setup(actor=self.hod, student_id=self.student.pk, values={})

    def confirm_body(self, issued, **changes):
        return {"uid": issued["uid"], "token": issued["token"], "new_password": self.password, **changes}


class StudentSetupTests(StudentSetupFixture, TestCase):
    def test_metadata_and_issuance_are_private_hod_only_and_least_privilege(self):
        initial = self.client.get(self.account_url).data
        self.assertIsNone(initial["account"])
        self.assertEqual(initial["preferred_username"], self.student.identifier_value)
        before_students = Student.objects.count()
        rejected = self.client.post(self.issue_url, {"username": "chosen-student"}, format="json")
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.seed_legacy_account(username="chosen-student",email="")
        response = self.client.post(self.issue_url, {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["expires_in"], settings.PASSWORD_RESET_TIMEOUT)
        self.assertIn("no-store", response.headers["Cache-Control"])
        account = User.objects.get(username="chosen-student")
        self.assertTrue(account.is_active)
        self.assertFalse(account.is_staff or account.is_superuser or account.has_usable_password())
        self.assertEqual(account.groups.count(), 0)
        self.assertEqual(account.user_permissions.count(), 0)
        self.assertEqual(Student.objects.count(), before_students)
        self.student.refresh_from_db()
        self.assertEqual(self.student.user_id, account.pk)
        metadata = self.client.get(self.account_url)
        self.assertEqual(metadata.data["account"], {"id": account.pk, "username": account.username,
            "email": "", "is_active": True, "setup_pending": True})
        self.assertIn("no-store", metadata.headers["Cache-Control"])
        self.assertNotIn("token", metadata.data["account"])
        self.assertNotIn("password", json.dumps(metadata.data))

    def test_student_sets_own_password_once_then_can_sign_in_to_linked_profile(self):
        issued = self.issue()
        public = APIClient()
        before_login = public.post("/api/auth/login/", {"username": "setup-student", "password": self.password}, format="json")
        self.assertEqual(before_login.status_code, 400)
        response = public.post(self.confirm_url, self.confirm_body(issued), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["username"], "setup-student")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(public.get("/api/auth/me/").status_code, 403)
        self.assertEqual(public.post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 400)
        logged_in = public.post("/api/auth/login/", {"username": "setup-student", "password": self.password}, format="json")
        self.assertEqual(logged_in.status_code, 200, logged_in.data)
        self.assertEqual(logged_in.data["role"], "student")
        profile = public.get("/api/me/student/")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["student_id"], str(self.student.pk))
        self.assertFalse(self.client.get(self.account_url).data["account"]["setup_pending"])

    def test_reissue_revokes_previous_token_even_within_the_same_second(self):
        issued = self.issue()
        reissued = self.client.post(self.issue_url, {}, format="json")
        self.assertEqual(reissued.status_code, 200, reissued.data)
        self.assertEqual(reissued.data["account"]["id"], issued["account"]["id"])
        self.assertNotEqual(reissued.data["token"], issued["token"])
        self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 400)
        self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(reissued.data), format="json").status_code, 200)

    def test_expired_token_and_reset_token_namespace_are_rejected(self):
        with patch.object(student_setup_tokens, "_now", return_value=datetime.now() - timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 2)):
            issued = self.issue()
        expired = APIClient().post(self.confirm_url, self.confirm_body(issued), format="json")
        self.assertEqual(expired.status_code, 400)
        account = User.objects.get(pk=issued["account"]["id"])
        ordinary = default_token_generator.make_token(account)
        self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(issued, token=ordinary), format="json").status_code, 400)
        fresh = self.client.post(self.issue_url, {}, format="json").data
        self.assertFalse(default_token_generator.check_token(account, fresh["token"]))

    def test_weak_password_does_not_consume_valid_link(self):
        issued = self.issue()
        response = APIClient().post(self.confirm_url, self.confirm_body(issued, new_password="123"), format="json")
        self.assertEqual(response.status_code, 400)
        account = User.objects.get(pk=issued["account"]["id"])
        self.assertFalse(account.has_usable_password())
        self.assertTrue(student_setup_tokens.check_token(account, issued["token"]))
        self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 200)

    def test_unknown_uids_and_invalid_tokens_return_the_same_error(self):
        issued = self.issue()
        errors = []
        for changes in ({"uid": "bad-base64"}, {"uid": urlsafe_base64_encode(force_bytes(99999999))},
                {"token": "invalid-token"}):
            response = APIClient().post(self.confirm_url, self.confirm_body(issued, **changes), format="json")
            self.assertEqual(response.status_code, 400)
            errors.append(response.data)
        self.assertEqual(errors[0], errors[1])
        self.assertEqual(errors[1], errors[2])

    def test_inactive_or_privileged_accounts_cannot_use_or_reissue_setup_link(self):
        issued = self.issue()
        for field in ("is_active", "is_staff", "is_superuser"):
            with self.subTest(field=field):
                User.objects.filter(pk=issued["account"]["id"]).update(**{field: field != "is_active"})
                self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 400)
                self.assertEqual(self.client.post(self.issue_url, {}, format="json").status_code, 400)
                User.objects.filter(pk=issued["account"]["id"]).update(**{field: field == "is_active"})

    def test_inactive_or_relinked_student_invalidates_setup_link(self):
        issued = self.issue()
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 400)
        self.assertEqual(self.client.post(self.issue_url, {}, format="json").status_code, 400)
        self.student.is_active = True
        self.student.user_id = None
        self.student.save(update_fields=["is_active", "user"])
        Student.objects.create(identifier_type="matriculation", identifier_value="SYNTHETIC/SETUP/002",
            full_name="Different Synthetic Student", phone_number="", admission_year=2026,
            mode_of_admission="utme", current_level=100, user_id=issued["account"]["id"])
        self.assertEqual(APIClient().post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 400)

    def test_usable_account_cannot_be_taken_over_or_have_identity_changed(self):
        issued = self.issue()
        self.assertEqual(self.client.post(self.issue_url, {"username": "replacement"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.issue_url, {"email": "replacement@example.test"}, format="json").status_code, 400)
        account = confirm_student_setup(**self.confirm_body(issued))
        old_password_hash = account.password
        self.assertEqual(self.client.post(self.issue_url, {}, format="json").status_code, 400)
        account.refresh_from_db()
        self.assertEqual(account.password, old_password_hash)

    def test_username_collision_and_inactive_student_create_no_orphan_accounts(self):
        User.objects.create_user("already-used", password=self.password)
        before = User.objects.count()
        collision = self.client.post(self.issue_url, {"username": "already-used"}, format="json")
        self.assertEqual(collision.status_code, 400)
        self.assertEqual(User.objects.count(), before)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.user_id)
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(self.issue_url, {"username": "new-pending"}, format="json").status_code, 400)
        self.assertFalse(User.objects.filter(username="new-pending").exists())
        self.assertEqual(AccountAdministrationAudit.objects.count(), 0)

    def test_metadata_and_setup_issuance_reject_staff_students_and_stale_hod(self):
        for user in (None, self.staff):
            client = APIClient()
            if user:
                client.force_authenticate(user)
            self.assertEqual(client.get(self.account_url).status_code, 403)
            self.assertEqual(client.post(self.issue_url, {"username": "no-access"}, format="json").status_code, 403)
        User.objects.filter(pk=self.hod.pk).update(is_superuser=False)
        self.assertEqual(self.client.get(self.account_url).status_code, 403)
        self.assertEqual(self.client.post(self.issue_url, {"username": "no-access"}, format="json").status_code, 403)
        self.assertFalse(User.objects.filter(username="no-access").exists())

    def test_new_inputs_reject_unknown_or_nonobject_bodies(self):
        issued = self.issue()
        for body in (None, [], [{"username": "unsafe"}], "invalid"):
            for url in (self.issue_url, self.confirm_url):
                response = self.client.generic("POST", url, json.dumps(body), content_type="application/json")
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.client.post(self.issue_url, {"is_superuser": True}, format="json").status_code, 400)
        self.assertEqual(APIClient().post(self.confirm_url, {**self.confirm_body(issued), "is_staff": True}, format="json").status_code, 400)

    def test_no_tokens_passwords_or_password_hashes_appear_in_audit(self):
        issued = self.issue()
        reissued = self.client.post(self.issue_url, {}, format="json").data
        confirm_student_setup(**self.confirm_body(reissued))
        events = list(AccountAdministrationAudit.objects.order_by("id"))
        self.assertEqual([event.action for event in events], ["student_setup_reissued", "student_setup_reissued", "student_setup_completed"])
        encoded = json.dumps([{**event.before, **event.after} for event in events])
        self.assertNotIn(issued["token"], encoded)
        self.assertNotIn(reissued["token"], encoded)
        self.assertNotIn(self.password, encoded)
        self.assertNotIn("password", encoded)

    def test_public_confirm_and_hod_issue_require_csrf_for_real_sessions(self):
        hod = APIClient(enforce_csrf_checks=True)
        hod.force_login(self.hod)
        self.assertEqual(hod.post(self.issue_url, {"username": "csrf-new"}, format="json").status_code, 403)
        issued = self.issue()
        public = APIClient(enforce_csrf_checks=True)
        self.assertEqual(public.post(self.confirm_url, self.confirm_body(issued), format="json").status_code, 403)
        csrf = public.get("/api/auth/csrf/").data["csrfToken"]
        accepted = public.post(self.confirm_url, self.confirm_body(issued), format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(public.get("/api/auth/me/").status_code, 403)

    @override_settings(REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
        "DEFAULT_THROTTLE_RATES": {"student_setup_confirm": "1/hour"}})
    def test_public_confirm_is_rate_limited(self):
        issued = self.issue()
        public = APIClient()
        self.assertEqual(public.post(self.confirm_url, self.confirm_body(issued, token="invalid"), format="json").status_code, 400)
        self.assertEqual(public.post(self.confirm_url, self.confirm_body(issued, token="invalid"), format="json").status_code, 429)

    def test_legacy_provision_and_link_recheck_demoted_hod_without_changes(self):
        unlinked = User.objects.create_user("legacy-unlinked", password=self.password)
        User.objects.filter(pk=self.hod.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            provision_student_account(user=self.hod, student=self.student, validated_data={
                "username": "legacy-provision", "email": "legacy@example.test", "password": self.password})
        with self.assertRaises(PermissionDenied):
            link_student_account(user=self.hod, student=self.student, account_id=unlinked.pk)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.user_id)


@skipUnless(connection.vendor == "postgresql", "Setup concurrency requires PostgreSQL row locks.")
class StudentSetupConcurrencyTests(StudentSetupFixture, TransactionTestCase):
    def test_two_first_password_submissions_consume_only_once(self):
        issued = self.issue()
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                confirm_student_setup(**self.confirm_body(issued))
                return "completed"
            except ValidationError:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda _: submit(), range(2)))
        self.assertCountEqual(outcomes, ["completed", "rejected"])
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="student_setup_completed").count(), 1)

    def test_reissue_and_confirmation_serialize_with_only_one_outcome(self):
        issued = self.issue()
        barrier = Barrier(2)

        def reissue():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                issue_student_setup(actor=User.objects.get(pk=self.hod.pk), student_id=self.student.pk, values={})
                return "reissued"
            except ValidationError:
                return "reissue-rejected"
            finally:
                close_old_connections()

        def confirm():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                confirm_student_setup(**self.confirm_body(issued))
                return "confirmed"
            except ValidationError:
                return "confirm-rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(reissue), workers.submit(confirm)]
            outcomes = [future.result(timeout=20) for future in futures]
        self.assertIn(outcomes, [["reissued", "confirm-rejected"], ["reissue-rejected", "confirmed"]])

    def test_hod_transfer_blocks_pending_setup_issue_and_fresh_authorization_rejects_it(self):
        transfer_locked, release_transfer, issuance_started = Event(), Event(), Event()
        pids = {}

        def pause_after_users(*args, **kwargs):
            result = locked_users(*args, **kwargs)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pids["transfer"] = cursor.fetchone()[0]
            transfer_locked.set()
            if not release_transfer.wait(10):
                raise RuntimeError("Timed out releasing synthetic HOD transfer.")
            return result

        def handover():
            close_old_connections()
            try:
                with patch("accounts.administration.locked_users", side_effect=pause_after_users):
                    complete_accepted_handover(actor=User.objects.get(pk=self.hod.pk), target_staff_id=self.staff.pk,
                        expected_target_username=self.staff.username, current_password=self.password, confirmation="TRANSFER HOD")
            finally:
                close_old_connections()

        def issue():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids["issue"] = cursor.fetchone()[0]
                issuance_started.set()
                issue_student_setup(actor=User.objects.get(pk=self.hod.pk), student_id=self.student.pk,
                    values={"username": "must-not-be-created"})
                return "created"
            except PermissionDenied:
                return "denied"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            transferring = workers.submit(handover)
            try:
                self.assertTrue(transfer_locked.wait(10))
                issuing = workers.submit(issue)
                self.assertTrue(issuance_started.wait(10))
                deadline, blocked = time.monotonic() + 10, False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pids["issue"]])
                        blocked = pids["transfer"] in cursor.fetchone()[0]
                    if blocked:
                        break
                    time.sleep(0.02)
                self.assertTrue(blocked, "Issuance must actually wait for the ownership transfer's user lock.")
            finally:
                release_transfer.set()
            transferring.result(timeout=15)
            self.assertEqual(issuing.result(timeout=15), "denied")
        self.student.refresh_from_db()
        self.assertIsNone(self.student.user_id)
        self.assertFalse(User.objects.filter(username="must-not-be-created").exists())
