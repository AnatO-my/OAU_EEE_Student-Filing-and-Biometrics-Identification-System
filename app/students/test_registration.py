from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from unittest import skipUnless

from accounts.models import AdviserAssignment
from academics.models import AcademicSession, Course, CourseOffering, Result
from .identity import identifier_key, resolve_student_identifier
from .models import Student, StudentIdentifier, StudentIdentityChange
from .services import create_student, promote_student_identifier


def profile(value="SYN/0001", **extra):
    return {"identifier_type": "matriculation", "identifier_value": value,
            "full_name": "Synthetic Student", "admission_year": 2026,
            "mode_of_admission": "utme", "current_level": 100, **extra}


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class StudentRegistrationTests(TestCase):
    def setUp(self):
        self.hod = get_user_model().objects.create_superuser("registration-hod", password="synthetic-password")
        self.adviser = get_user_model().objects.create_user("registration-adviser", is_staff=True)
        self.adviser.user_permissions.add(*Permission.objects.filter(content_type__app_label="students",
            codename__in=["view_student", "add_student", "change_student"]))
        AdviserAssignment.objects.create(staff=self.adviser, academic_session="2026/2027", level=100)
        self.client = APIClient()
        self.client.force_authenticate(self.adviser)

    def test_registration_keeps_text_identity_and_omits_missing_phone_and_login(self):
        response = self.client.post("/api/students/", profile(" EEE/0001 ", surname="Synthetic"), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["identifier_value"], "EEE/0001")
        self.assertEqual(response.data["phone_number"], "")
        self.assertNotIn("surname", response.data)
        student = Student.objects.get(pk=response.data["student_id"])
        self.assertEqual(student.surname, "Synthetic")
        self.assertIsNone(student.user_id)
        self.assertEqual(StudentIdentifier.objects.get(identifier_key="eee/0001").student, student)

    def test_case_space_duplicates_and_alias_reuse_return_generic_error(self):
        outside = Student.objects.create(**profile("EEE/0001", current_level=300, full_name="Outside private name"))
        response = self.client.post("/api/students/", profile(" eee/0001 "), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(outside.full_name, str(response.data))
        self.assertNotIn(str(outside.pk), str(response.data))
        self.assertEqual(Student.objects.count(), 1)

    def test_exact_lookup_does_not_fuzzy_match_or_disclose_outside_scope(self):
        student = Student.objects.create(**profile("EEE/0001"))
        outside = Student.objects.create(**profile("PRIVATE/0002", current_level=300))
        response = self.client.get("/api/students/lookup/", {"identifier_type": "matriculation", "identifier_value": " eee/0001 "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["student_id"], str(student.pk))
        for value in ("EEE/000", outside.identifier_value, "MISSING/0001"):
            response = self.client.get("/api/students/lookup/", {"identifier_type": "matriculation", "identifier_value": value})
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(str(outside.pk), str(response.data))

    def test_bad_identifiers_are_rejected_before_the_database(self):
        for value in ("", "  ", "EEE/\x00001", 12345):
            with self.subTest(value=value):
                response = self.client.post("/api/students/", profile(value), format="json")
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Student.objects.exists())

    def test_registration_and_identity_changes_obey_role_boundaries(self):
        response = self.client.post("/api/students/", profile(current_level=300), format="json")
        self.assertEqual(response.status_code, 403)
        student = Student.objects.create(**profile())
        response = self.client.patch(f"/api/students/{student.pk}/", {"identifier_value": "NEW/001"}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(f"/api/students/{student.pk}/promote-identifier/", {
            "identifier_value": "NEW/001", "expected_identifier_type": "matriculation", "expected_identifier_value": student.identifier_value,
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_promotion_preserves_profile_account_results_and_old_identifier(self):
        account = get_user_model().objects.create_user("linked-registration-student")
        student = Student.objects.create(**profile("000012345", identifier_type="utme", user=account))
        session = AcademicSession.objects.create(name="2026/2027")
        course = Course.objects.create(code="REG101", title="Synthetic Registration Course")
        offering = CourseOffering.objects.create(course=course, academic_session=session, semester="harmattan", level=100, credit_units=3)
        result = Result.objects.create(student=student, offering=offering, credit_units=3, score=70)
        self.client.force_authenticate(self.hod)
        response = self.client.post(f"/api/students/{student.pk}/promote-identifier/", {
            "identifier_value": "EEE/0001", "expected_identifier_type": "utme", "expected_identifier_value": "000012345",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        student.refresh_from_db(); result.refresh_from_db()
        self.assertEqual(student.identifier_value, "EEE/0001")
        self.assertEqual(student.user_id, account.pk)
        self.assertEqual(result.student_id, student.pk)
        self.assertEqual(resolve_student_identifier("utme", "000012345").pk, student.pk)
        self.assertEqual(resolve_student_identifier("matriculation", "eee/0001").pk, student.pk)
        self.assertIsNone(resolve_student_identifier("utme", "EEE/0001"))
        self.assertEqual(StudentIdentityChange.objects.get(student=student).actor, self.hod)
        response = self.client.post("/api/students/", profile("000012345", identifier_type="utme"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Student.objects.count(), 1)

    def test_conflicting_or_stale_promotion_never_changes_either_student(self):
        student = Student.objects.create(**profile("000012345", identifier_type="utme"))
        other = Student.objects.create(**profile("EEE/0001"))
        self.client.force_authenticate(self.hod)
        for value, expected in (("eee/0001", "000012345"), ("NEW/001", "wrong-old-value")):
            response = self.client.post(f"/api/students/{student.pk}/promote-identifier/", {
                "identifier_value": value, "expected_identifier_type": "utme", "expected_identifier_value": expected,
            }, format="json")
            self.assertEqual(response.status_code, 400)
        student.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(student.identifier_value, "000012345")
        self.assertEqual(other.identifier_value, "EEE/0001")
        self.assertFalse(StudentIdentityChange.objects.exists())

    def test_bulk_fixture_writes_reserve_aliases_and_cannot_bypass_duplicates(self):
        students = Student.objects.bulk_create([Student(**profile("BULK/001")), Student(**profile("BULK/002"))])
        self.assertEqual(StudentIdentifier.objects.count(), 2)
        self.assertEqual(resolve_student_identifier("matriculation", "bulk/001").pk, students[0].pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Student.objects.bulk_create([Student(**profile("bulk/001"))])
        with self.assertRaises(ValueError):
            Student.objects.filter(pk=students[0].pk).update(identifier_value="UNRESERVED/001")

    def test_partial_save_cannot_reserve_an_unpersisted_identity(self):
        student = Student.objects.create(**profile())
        student.identifier_value = "UNPERSISTED/001"
        with self.assertRaisesMessage(ValueError, "partial save"):
            student.save(update_fields=["full_name"])
        student.refresh_from_db()
        self.assertEqual(student.identifier_value, "SYN/0001")
        self.assertFalse(StudentIdentifier.objects.filter(identifier_key="unpersisted/001").exists())


@skipUnless(connection.vendor == "postgresql", "Requires independent PostgreSQL connections.")
class StudentRegistrationConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_registrations_create_one_student(self):
        hod = get_user_model().objects.create_superuser("registration-race-hod", password="synthetic-password")
        barrier = Barrier(2)
        def register(value):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=hod.pk)
                barrier.wait(timeout=15)
                try:
                    create_student(user=user, validated_data=profile(value))
                    return "created"
                except ValidationError:
                    return "duplicate"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(register, ["RACE/001", " race/001 "]))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(StudentIdentifier.objects.count(), 1)

    def test_promotion_and_registration_cannot_claim_the_same_matric(self):
        hod = get_user_model().objects.create_superuser("promotion-race-hod", password="synthetic-password")
        original = Student.objects.create(**profile("000012345", identifier_type="utme"))
        barrier = Barrier(2)
        def change(promote):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=hod.pk)
                barrier.wait(timeout=15)
                try:
                    if promote:
                        promote_student_identifier(user=user, student=original, identifier_value="RACE/001",
                            expected_identifier_type="utme", expected_identifier_value="000012345")
                    else:
                        create_student(user=user, validated_data=profile("race/001"))
                    return "created"
                except ValidationError:
                    return "duplicate"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(change, [True, False]))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(Student.objects.filter(identifier_key="race/001").count(), 1)
        registry = StudentIdentifier.objects.get(identifier_key="race/001")
        self.assertEqual(Student.objects.get(identifier_key="race/001").pk, registry.student_id)


class StudentIdentityMigrationTests(TransactionTestCase):
    old_target = [("students", "0006_merge_academic_status_surname")]

    def test_migration_preserves_existing_display_uuid_and_registers_lookup_key(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(self.old_target)
            apps = executor.loader.project_state(self.old_target).apps
            OldStudent = apps.get_model("students", "Student")
            original = OldStudent.objects.create(**profile("EEE/0001"))
            MigrationExecutor(connection).migrate(latest)
            student = Student.objects.get(pk=original.pk)
            self.assertEqual(student.identifier_value, "EEE/0001")
            self.assertEqual(student.identifier_key, "eee/0001")
            self.assertEqual(StudentIdentifier.objects.get(identifier_key="eee/0001").student_id, original.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_ambiguous_existing_identities_fail_without_merging_or_deleting(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(self.old_target)
            apps = executor.loader.project_state(self.old_target).apps
            OldStudent = apps.get_model("students", "Student")
            first = OldStudent.objects.create(**profile("EEE/0001"))
            second = OldStudent.objects.create(**profile(" eee/0001 "))
            with self.assertRaisesMessage(RuntimeError, "case/space-colliding"):
                MigrationExecutor(connection).migrate(latest)
            self.assertEqual(OldStudent.objects.count(), 2)
            self.assertEqual(OldStudent.objects.get(pk=first.pk).identifier_value, "EEE/0001")
            self.assertEqual(OldStudent.objects.get(pk=second.pk).identifier_value, " eee/0001 ")
            # Remove only the deliberately conflicting synthetic row so the test
            # schema can be restored; the migration itself never changes it.
            second.delete()
        finally:
            MigrationExecutor(connection).migrate(latest)
