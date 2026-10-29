"""Synthetic HOD administration, authorization and handover regression tests."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Event
import time
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from academics.models import AcademicSession, CurrentAcademicSession
from students.models import Student
from .administration import MANAGED_PERMISSIONS, locked_users, save_assignment, transfer_hod
from .models import AccountAdministrationAudit, AdviserAssignment, HODMessage, User
from .services import send_hod_message


def complete_accepted_handover(*, actor, target_staff_id, **unused_legacy_confirmation):
    """Exercise the accepted lifecycle where old tests need a completed transfer."""
    from django.db import transaction
    from accounts import administration
    from accounts.batch_services import offer_handover, accept_handover
    with transaction.atomic():
        administration.locked_users(actor, target_staff_id)
        offered = offer_handover(actor=actor, target_id=target_staff_id)
        return accept_handover(actor=User.objects.get(pk=target_staff_id), handover_id=offered.pk)



class AdministrationFixture:
    password = "Synthetic!HOD-7281-Cedar"

    def setUp(self):
        super().setUp()
        self.hod = User.objects.create_superuser("admin-hod", "hod@example.test", self.password)
        self.staff = User.objects.create_user("admin-staff", password=self.password, is_staff=True)
        self.other = User.objects.create_user("admin-other", password=self.password, is_staff=True)
        self.student_user = User.objects.create_user("admin-student", password=self.password)
        self.student = Student.objects.create(identifier_type="matriculation", identifier_value="SYNTHETIC/0001",
            full_name="Synthetic Student", phone_number="", admission_year=2026,
            mode_of_admission="utme", current_level=100, user=self.student_user)
        self.session = AcademicSession.objects.create(name="2026/2027")
        CurrentAcademicSession.objects.update_or_create(pk=1, defaults={"academic_session": self.session,
            "updated_by": self.hod})
        self.client = APIClient()
        self.client.force_authenticate(self.hod)

    def handover(self, **changes):
        return {"target_staff_id": self.staff.pk, "expected_target_username": self.staff.username,
            "current_password": self.password, "confirmation": "TRANSFER HOD", **changes}


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class AccountAdministrationTests(AdministrationFixture, TestCase):
    def test_all_administration_endpoints_require_fresh_active_hod(self):
        urls = ["administration-options/", "staff/", "adviser-assignments/"]
        for user in (None, self.staff, self.student_user):
            client = APIClient()
            if user:
                client.force_authenticate(user)
            for suffix in urls:
                with self.subTest(user=user, suffix=suffix):
                    self.assertEqual(client.get("/api/accounts/" + suffix).status_code, 403)
            self.assertEqual(client.post("/api/accounts/transfer-hod/", self.handover(), format="json").status_code, 403)
        # force_authenticate retains an old in-memory instance; service rechecks DB.
        User.objects.filter(pk=self.hod.pk).update(is_superuser=False)
        self.assertEqual(self.client.get("/api/accounts/staff/").status_code, 403)
        self.assertEqual(self.client.post("/api/accounts/staff/", {}, format="json").status_code, 403)

    def test_options_catalog_has_only_grantable_codes_and_recorded_sessions(self):
        response = self.client.get("/api/accounts/administration-options/")
        self.assertEqual(response.status_code, 200)
        codes = {item["code"] for item in response.data["permissions"]}
        self.assertEqual(codes, MANAGED_PERMISSIONS)
        self.assertFalse(any(code.startswith("auth.") or code.startswith("accounts.change_") for code in codes))
        self.assertEqual(response.data["academic_sessions"], [{"id": self.session.pk, "name": "2026/2027"}])
        self.assertEqual(response.data["current_academic_session"], "2026/2027")

    def test_create_staff_validates_password_never_returns_or_audits_credentials(self):
        body = {"username": "created-adviser", "password": self.password,
            "first_name": "Synthetic", "email": "new@example.test", "permission_codes": ["students.view_student"]}
        weak = self.client.post("/api/accounts/staff/", {**body, "password": "123"}, format="json")
        self.assertEqual(weak.status_code, 400)
        self.assertFalse(User.objects.filter(username=body["username"]).exists())
        response = self.client.post("/api/accounts/staff/", body, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(username=body["username"])
        self.assertTrue(created.is_active and created.is_staff and not created.is_superuser)
        self.assertTrue(created.check_password(self.password))
        self.assertEqual(response.data["direct_permissions"], ["students.view_student"])
        audit = AccountAdministrationAudit.objects.get(action="staff_created")
        serialized = json.dumps({"response": response.data, "before": audit.before, "after": audit.after})
        self.assertNotIn(self.password, serialized)
        self.assertNotIn("password", serialized)
        self.assertEqual(self.client.post("/api/accounts/staff/", body, format="json").status_code, 400)

    def test_managed_permission_updates_preserve_groups_and_unmanaged_direct_grants(self):
        group = Group.objects.create(name="Synthetic inherited grants")
        inherited = Permission.objects.get(content_type__app_label="academics", codename="view_result")
        group.permissions.add(inherited)
        self.staff.groups.add(group)
        outside = Permission.objects.get(content_type__app_label="students", codename="export_student")
        old = Permission.objects.get(content_type__app_label="students", codename="view_student")
        self.staff.user_permissions.add(outside, old)
        response = self.client.patch(f"/api/accounts/staff/{self.staff.pk}/",
            {"first_name": "Updated", "permission_codes": ["students.change_student"]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["direct_permissions"], ["students.change_student", "students.export_student"])
        self.assertEqual(response.data["inherited_permissions"], ["academics.view_result"])
        self.assertEqual(response.data["groups"], [group.name])
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.has_perm("academics.view_result"))
        self.assertFalse(self.staff.has_perm("students.view_student"))
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="staff_updated").count(), 1)

    def test_escalation_role_student_self_and_hod_edits_are_rejected(self):
        for payload in ({"is_superuser": True}, {"is_staff": False}, {"groups": [1]},
                {"username": "replacement"}, {"password": self.password},
                {"permission_codes": ["accounts.change_user"]},
                {"permission_codes": ["students.view_student", "students.view_student"]}):
            with self.subTest(payload=list(payload)):
                response = self.client.patch(f"/api/accounts/staff/{self.staff.pk}/", payload, format="json")
                self.assertEqual(response.status_code, 400)
        for target in (self.hod, User.objects.create_superuser("second-hod", "second@example.test", self.password)):
            self.assertEqual(self.client.patch(f"/api/accounts/staff/{target.pk}/", {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/accounts/staff/{self.student_user.pk}/", {"first_name": "Changed"}, format="json").status_code, 404)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_superuser)
        self.assertEqual(AccountAdministrationAudit.objects.count(), 0)

    def test_staff_listing_is_paginated_searchable_and_has_safe_transfer_flags(self):
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        response = self.client.get("/api/accounts/staff/?is_active=false&search=admin-staff")
        self.assertEqual(response.data["count"], 1)
        self.assertFalse(response.data["results"][0]["can_transfer"])
        active = self.client.get("/api/accounts/staff/?is_active=true")
        self.assertEqual(active.data["count"], 2)
        self.assertNotIn(self.student_user.pk, [row["id"] for row in active.data["results"]])
        self.assertEqual(self.client.get("/api/accounts/staff/?is_active=unknown").status_code, 400)

    def test_adviser_assignments_create_update_reassign_and_validate_duplicates(self):
        body = {"staff_id": self.staff.pk, "academic_session": "2026/2027", "level": 100, "is_active": True}
        response = self.client.post("/api/accounts/adviser-assignments/", body, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        assignment_id = response.data["id"]
        self.assertEqual(self.client.post("/api/accounts/adviser-assignments/", body, format="json").status_code, 400)
        updated = self.client.patch(f"/api/accounts/adviser-assignments/{assignment_id}/",
            {"staff_id": self.other.pk, "level": 300, "is_active": False}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["staff_username"], self.other.username)
        self.assertFalse(updated.data["is_active"])
        self.assertEqual(self.client.get(f"/api/accounts/adviser-assignments/?staff_id={self.staff.pk}").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/accounts/adviser-assignments/?staff_id={self.other.pk}").data["count"], 1)
        self.assertEqual(AccountAdministrationAudit.objects.count(), 2)

    def test_adviser_assignments_reject_student_inactive_hod_or_unknown_session(self):
        body = {"staff_id": self.staff.pk, "academic_session": "2026/2027", "level": 100}
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        for changes in ({"staff_id": self.staff.pk}, {"staff_id": self.student_user.pk},
                {"staff_id": self.hod.pk}, {"staff_id": self.other.pk, "academic_session": "2028/2029"},
                {"staff_id": self.other.pk, "level": 0}):
            response = self.client.post("/api/accounts/adviser-assignments/", {**body, **changes}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(AdviserAssignment.objects.count(), 0)

    def test_existing_assignment_can_be_deactivated_after_staff_deactivation_or_hod_promotion(self):
        for user, changed_field in ((self.staff, "is_active"), (self.other, "is_superuser")):
            assignment = AdviserAssignment.objects.create(staff=user, academic_session="2026/2027", level=100)
            setattr(user, changed_field, changed_field == "is_superuser")
            user.save(update_fields=[changed_field])
            response = self.client.patch(f"/api/accounts/adviser-assignments/{assignment.pk}/",
                {"is_active": False}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertFalse(response.data["is_active"])
            self.assertEqual(self.client.patch(f"/api/accounts/adviser-assignments/{assignment.pk}/",
                {"is_active": True}, format="json").status_code, 400)

    def test_hod_transfer_reauthenticates_and_rejects_wrong_or_ineligible_target(self):
        for changes in ({"current_password": "wrong"}, {"expected_target_username": "someone-else"},
                {"confirmation": "yes"}, {"target_staff_id": self.hod.pk},
                {"target_staff_id": self.student_user.pk}, {"target_staff_id": 999999}):
            response = self.client.post("/api/accounts/transfer-hod/", self.handover(**changes), format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.staff.set_unusable_password()
        self.staff.save(update_fields=["password"])
        self.assertEqual(self.client.post("/api/accounts/transfer-hod/", self.handover(), format="json").status_code, 400)
        self.assertEqual(User.objects.filter(is_superuser=True, is_staff=True, is_active=True).count(), 1)
        self.assertEqual(AccountAdministrationAudit.objects.count(), 0)

    def test_transfer_keeps_other_hods_and_old_staff_active_with_existing_grants(self):
        second_hod = User.objects.create_superuser("unrelated-hod", "other@example.test", self.password)
        permission = Permission.objects.get(content_type__app_label="students", codename="view_student")
        self.hod.user_permissions.add(permission)
        response = self.client.post("/api/workflows/handover/", {"target_id": self.staff.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.hod.refresh_from_db()
        self.assertTrue(self.hod.is_superuser)
        recipient = APIClient()
        recipient.force_authenticate(self.staff)
        accepted = recipient.post("/api/workflows/handover/", {"handover_id": response.data["id"]}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.hod.refresh_from_db()
        self.staff.refresh_from_db()
        second_hod.refresh_from_db()
        self.assertTrue(self.hod.is_active and self.hod.is_staff and not self.hod.is_superuser)
        self.assertTrue(self.hod.has_perm("students.view_student"))
        self.assertTrue(self.staff.is_superuser and self.staff.is_active)
        self.assertTrue(second_hod.is_superuser)
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="hod_transfer_accepted").count(), 1)
        self.assertEqual(self.client.get("/api/accounts/staff/").status_code, 403)
        new_hod_client = APIClient()
        new_hod_client.force_authenticate(self.staff)
        self.assertEqual(new_hod_client.get("/api/accounts/staff/").status_code, 200)

    def test_authenticated_session_requires_csrf_for_staff_mutation(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.hod)
        response = client.post("/api/accounts/staff/", {"username": "csrf-new", "password": self.password}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="csrf-new").exists())

    def test_malformed_administration_bodies_return_400_without_mutation(self):
        for body in (None, [], [{"is_superuser": True}], "not-an-object"):
            for url in ("/api/accounts/staff/", "/api/accounts/adviser-assignments/", "/api/accounts/transfer-hod/"):
                with self.subTest(url=url, body=body):
                    response = self.client.generic("POST", url, data=json.dumps(body), content_type="application/json")
                    self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(AccountAdministrationAudit.objects.count(), 0)

    def test_loaded_hod_cannot_send_any_audience_after_ownership_transfer(self):
        AdviserAssignment.objects.create(staff=self.other, academic_session="2026/2027", level=100)
        complete_accepted_handover(actor=self.hod, **self.handover())
        self.assertTrue(self.hod.is_superuser)  # The stale instance still claims HOD.
        for audience in ({"audience": "adviser", "adviser_id": self.other.pk},
                {"audience": "individual", "recipient_id": self.student.pk},
                {"audience": "level", "level": 100}):
            with self.subTest(audience=audience["audience"]), self.assertRaises(PermissionDenied):
                send_hod_message(user=self.hod, validated_data={**audience, "subject": "Stale HOD",
                    "body": "This message must never be saved."})
        self.assertEqual(HODMessage.objects.count(), 0)


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL.")
class HODTransferConcurrencyTests(AdministrationFixture, TransactionTestCase):
    def test_two_transfers_from_same_hod_allow_only_one_new_owner(self):
        barrier = Barrier(2)

        def attempt(target):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.hod.pk)
                barrier.wait(timeout=10)
                complete_accepted_handover(actor=actor, target_staff_id=target.pk, expected_target_username=target.username,
                    current_password=self.password, confirmation="TRANSFER HOD")
                return "won"
            except PermissionDenied:
                return "denied"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(attempt, [self.staff, self.other]))
        self.assertCountEqual(outcomes, ["won", "denied"])
        self.assertEqual(User.objects.filter(is_superuser=True, is_staff=True, is_active=True).count(), 1)
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="hod_transfer_accepted").count(), 1)

    @override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
    def test_assignment_edit_and_hod_message_follow_compatible_user_then_assignment_locks(self):
        assignment = AdviserAssignment.objects.create(staff=self.staff, academic_session="2026/2027", level=100)
        users_locked, release_edit, message_started = Event(), Event(), Event()
        pids = {}

        def pause_after_users(*args, **kwargs):
            result = locked_users(*args, **kwargs)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pids["edit"] = cursor.fetchone()[0]
            users_locked.set()
            if not release_edit.wait(10):
                raise RuntimeError("Timed out releasing the synthetic assignment edit.")
            return result

        def edit():
            close_old_connections()
            try:
                with patch("accounts.administration.locked_users", side_effect=pause_after_users):
                    return save_assignment(actor=User.objects.get(pk=self.hod.pk), assignment_id=assignment.pk,
                        values={"level": 300}).pk
            finally:
                close_old_connections()

        def message():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids["message"] = cursor.fetchone()[0]
                message_started.set()
                return send_hod_message(user=User.objects.get(pk=self.hod.pk), validated_data={
                    "audience": "adviser", "adviser_id": self.staff.pk,
                    "subject": "Synthetic advising update", "body": "Synthetic lock-order regression."}).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            editing = workers.submit(edit)
            try:
                self.assertTrue(users_locked.wait(10))
                sending = workers.submit(message)
                self.assertTrue(message_started.wait(10))
                blocked = False
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pids["message"]])
                        blocked = pids["edit"] in cursor.fetchone()[0]
                    if blocked:
                        break
                    time.sleep(0.02)
                self.assertTrue(blocked, "The message must actually contend with the assignment edit.")
            finally:
                release_edit.set()
            self.assertEqual(editing.result(timeout=15), assignment.pk)
            message_id = sending.result(timeout=15)
        assignment.refresh_from_db()
        self.assertEqual(assignment.level, 300)
        self.assertEqual(HODMessage.objects.get(pk=message_id).adviser_recipients.get().pk, self.staff.pk)
        self.assertEqual(AccountAdministrationAudit.objects.filter(action="adviser_updated").count(), 1)
