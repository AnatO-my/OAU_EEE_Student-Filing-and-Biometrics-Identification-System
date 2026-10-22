import csv
import io
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from academics.models import AcademicSession, Course, CourseOffering, CurrentAcademicSession, GradingScale, Result
from students.models import Student
from accounts.models import AdviserAssignment

from .format import RESULT_COLUMNS, ROSTER_COLUMNS, parse_csv
from .models import ImportBatch, ImportChange, ImportMutex
from .services import ImportConflict, commit_import, create_preview, public_batch, refresh_preview


def csv_text(columns, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(field, "") for field in columns])
    return output.getvalue()


class ImportFixture:
    def setUp(self):
        super().setUp()
        # TransactionTestCase flushes data-migration rows between tests. Define
        # this fixture explicitly so real contention tests remain independent.
        ImportMutex.objects.get_or_create(pk=1)
        scale = GradingScale.objects.create(name="Synthetic import scale", is_published=True, bands=[
            {"minimum": "0", "maximum": "40", "grade_point": "0"},
            {"minimum": "40", "maximum": "45", "grade_point": "1"},
            {"minimum": "45", "maximum": "50", "grade_point": "2"},
            {"minimum": "50", "maximum": "60", "grade_point": "3"},
            {"minimum": "60", "maximum": "70", "grade_point": "4"},
            {"minimum": "70", "maximum": "100", "grade_point": "5"},
        ])
        self.hod = get_user_model().objects.create_user(username="import-hod", is_staff=True, is_superuser=True)
        self.staff = get_user_model().objects.create_user(username="import-adviser", is_staff=True)
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label__in=["students", "academics"]))
        self.assignment = AdviserAssignment.objects.create(staff=self.staff, academic_session="2026/2027", level=100)
        self.student = Student.objects.create(identifier_type="matriculation", identifier_value="000123",
            full_name="Existing Student", surname="Student", phone_number="", admission_year=2026,
            mode_of_admission="utme", current_level=100)
        self.session = AcademicSession.objects.create(name="2026/2027")
        CurrentAcademicSession.objects.update_or_create(pk=1, defaults={"academic_session": self.session, "updated_by": self.hod})
        self.course = Course.objects.create(code="EEE101", title="Synthetic Circuits")
        self.offering = CourseOffering.objects.create(course=self.course, academic_session=self.session,
            semester="harmattan", level=100, credit_units=3, grading_scale=scale)

    def roster_row(self, **values):
        return {"identifier_type": "matriculation", "identifier_value": "000234", "full_name": "New Student",
            "surname": "Student", "phone_number": "", "admission_year": "2026", "mode_of_admission": "utme", "current_level": "100", **values}

    def result_row(self, **values):
        return {"identifier_type": "matriculation", "identifier_value": "000123", "course_code": "EEE101",
            "academic_session": "2026/2027", "semester": "harmattan", "attempt_number": "1", "score": "76.00", **values}

    def preview(self, kind="results", rows=None, user=None, request_id=None, columns=None):
        return create_preview(user=user or self.hod, kind=kind, request_id=request_id or uuid.uuid4(),
            filename="synthetic.csv", csv_text=csv_text(columns or (ROSTER_COLUMNS if kind == "roster" else RESULT_COLUMNS), rows or [self.result_row()]))[0]

    def commit(self, batch, user=None, approvals=None):
        return commit_import(user=user or self.hod, batch_id=batch.pk, preview_digest=batch.preview_digest, correction_approvals=approvals or [])


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class RecordImportTests(ImportFixture, TestCase):
    def test_roster_registration_and_commit_retry_create_only_one_profile(self):
        batch = self.preview("roster", [self.roster_row()])
        self.assertEqual(batch.preview["summary"]["new_students"], 1)
        committed, replayed = self.commit(batch)
        self.assertFalse(replayed)
        student = Student.objects.get(identifier_value="000234")
        self.assertIsNone(student.user_id)
        self.assertEqual(student.phone_number, "")
        retry, replayed = self.commit(batch)
        self.assertTrue(replayed)
        self.assertEqual(retry.receipt, committed.receipt)
        self.assertEqual(Student.objects.filter(identifier_value="000234").count(), 1)
        self.assertEqual(ImportChange.objects.filter(batch=batch).count(), 1)
        another = self.preview("roster", [self.roster_row()])
        self.assertEqual(another.preview["summary"]["unchanged"], 1)

    def test_identifiers_are_text_with_leading_zeros_and_case_insensitive_letters(self):
        first = self.preview("roster", [self.roster_row(identifier_value="MAT/0007")])
        self.commit(first)
        repeated = self.preview("roster", [self.roster_row(identifier_value="mat/0007")])
        self.assertEqual(repeated.preview["summary"]["unchanged"], 1)
        self.assertEqual(self.preview("roster", [self.roster_row(identifier_value="MAT/7")]).preview["summary"]["new_students"], 1)

    def test_repeated_or_conflicting_profile_rows_never_overwrite_biodata(self):
        row = self.roster_row(identifier_value="000123", full_name="Different Person")
        batch = self.preview("roster", [row, self.roster_row()])
        self.assertEqual(batch.preview["rows"][0]["code"], "identity_conflict")
        with self.assertRaises(ImportConflict):
            self.commit(batch)
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Existing Student")
        self.assertFalse(Student.objects.filter(identifier_value="000234").exists())

    def test_result_import_and_reimport_reuse_student_and_result(self):
        batch = self.preview()
        committed, _ = self.commit(batch)
        result = Result.objects.get(student=self.student)
        self.assertFalse(result.is_verified)
        self.assertEqual(result.score, Decimal("76.00"))
        self.assertEqual(committed.receipt["created_results"], 1)
        result.is_verified = True
        result.save(update_fields=["is_verified"])
        repeated = self.preview()
        self.assertEqual(repeated.preview["summary"]["unchanged"], 1)
        self.commit(repeated)
        result.refresh_from_db()
        self.assertTrue(result.is_verified)
        self.assertEqual(Result.objects.count(), 1)
        self.assertEqual(Student.objects.count(), 1)

    def test_differing_score_requires_reasoned_approval_and_clears_verification(self):
        result = Result.objects.create(student=self.student, offering=self.offering, score=65,
            credit_units=3, is_verified=True)
        batch = self.preview()
        self.assertEqual(batch.preview["rows"][0]["action"], "correction")
        with self.assertRaises(ValidationError):
            self.commit(batch)
        with self.assertRaises(ValidationError):
            self.commit(batch, approvals=[{"row_number": 2, "reason": "Invalid\x00reason"}])
        result.refresh_from_db()
        self.assertEqual(result.score, 65)
        self.commit(batch, approvals=[{"row_number": 2, "reason": "Reviewed corrected master sheet"}])
        result.refresh_from_db()
        self.assertEqual(result.score, 76)
        self.assertFalse(result.is_verified)
        change = ImportChange.objects.get(batch=batch)
        self.assertEqual(change.before["score"], "65.00")
        self.assertEqual(change.after["score"], "76.00")
        self.assertEqual(change.reason, "Reviewed corrected master sheet")

    def test_new_result_after_preview_invalidates_entire_batch_without_other_writes(self):
        second = Course.objects.create(code="EEE102", title="Synthetic Physics")
        CourseOffering.objects.create(course=second, academic_session=self.session, semester="harmattan", level=100, credit_units=2)
        batch = self.preview(rows=[self.result_row(), self.result_row(course_code="EEE102")])
        Result.objects.create(student=self.student, offering=self.offering, score=10, credit_units=3)
        with self.assertRaises(ImportConflict):
            self.commit(batch)
        self.assertEqual(Result.objects.count(), 1)
        batch.refresh_from_db()
        self.assertEqual(batch.status, "preview")
        self.assertEqual(ImportChange.objects.count(), 0)

    def test_unknown_student_remains_staged_until_registered_then_refreshed(self):
        before_students = Student.objects.count()
        batch = self.preview(rows=[self.result_row(identifier_value="000234"), self.result_row()])
        self.assertEqual(batch.preview["rows"][0]["code"], "unknown_student")
        self.assertEqual(batch.preview["summary"]["new_students"], 0)
        self.assertEqual(Student.objects.count(), before_students)
        self.assertFalse(public_batch(batch)["can_commit"])
        with self.assertRaises(ImportConflict):
            self.commit(batch)
        self.assertEqual(Student.objects.count(), before_students)
        self.assertFalse(Student.objects.filter(identifier_value="000234").exists())
        self.assertEqual(Result.objects.count(), 0)
        # Registration is a separate action, never a result-import side effect.
        Student.objects.create(identifier_type="matriculation", identifier_value="000234",
            full_name="Separately Registered Student", phone_number="", admission_year=2026,
            mode_of_admission="utme", current_level=100)
        refreshed = refresh_preview(user=self.hod, batch_id=batch.pk)
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(refreshed.preview["summary"]["new_results"], 2)
        self.commit(refreshed)
        self.assertEqual(Result.objects.count(), 2)
        self.assertEqual(Student.objects.count(), before_students + 1)

    def test_optional_name_conflict_blocks_result_matching(self):
        batch = self.preview(rows=[self.result_row(full_name="Another Person")], columns=RESULT_COLUMNS + ["full_name"])
        self.assertEqual(batch.preview["rows"][0]["code"], "identity_conflict")
        with self.assertRaises(ImportConflict):
            self.commit(batch)

    def test_duplicate_rows_do_not_become_another_attempt(self):
        batch = self.preview(rows=[self.result_row(), self.result_row()])
        self.assertEqual(batch.preview["rows"][1]["code"], "duplicate_row")
        with self.assertRaises(ImportConflict):
            self.commit(batch)
        self.assertEqual(Result.objects.count(), 0)

    def test_zero_is_valid_but_blank_nonfinite_and_ambiguous_scores_are_blocked(self):
        self.assertEqual(self.preview(rows=[self.result_row(score="0")]).preview["summary"]["new_results"], 1)
        for score in ("", "NaN", "Infinity", "1e2", "O0", "-1", "100.01", "2.333"):
            with self.subTest(score=score):
                self.assertEqual(self.preview(rows=[self.result_row(score=score)]).preview["summary"]["blocked"], 1)

    def test_request_id_is_bound_to_immutable_source(self):
        request_id = uuid.uuid4()
        batch = self.preview(request_id=request_id)
        self.assertEqual(self.preview(request_id=request_id).pk, batch.pk)
        with self.assertRaises(ImportConflict):
            self.preview(request_id=request_id, rows=[self.result_row(score="55")])

    def test_staff_access_is_scoped_and_rechecked_after_revocation(self):
        batch = self.preview(user=self.staff)
        self.assignment.is_active = False
        self.assignment.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.commit(batch, user=self.staff)
        self.assertEqual(Result.objects.count(), 0)
        unavailable = self.preview(user=self.staff)
        row = unavailable.preview["rows"][0]
        self.assertEqual(row["code"], "unavailable_student")
        self.assertNotIn("student_id", row)

    def test_fresh_permissions_do_not_trust_cached_user_permissions(self):
        batch = self.preview(user=self.staff)
        self.staff.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            self.commit(batch, user=self.staff)
        self.assertEqual(Result.objects.count(), 0)

    def test_historical_sheet_never_changes_current_level(self):
        self.student.current_level = 300
        self.student.save(update_fields=["current_level"])
        batch = self.preview()
        self.commit(batch)
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_level, 300)

    def test_malformed_headers_extra_columns_control_characters_and_large_files_rejected(self):
        for data in ("identifier_value,score\n1,5\n", csv_text(RESULT_COLUMNS + ["unexpected"], [self.result_row()]),
                     csv_text(RESULT_COLUMNS, [self.result_row(identifier_value="a\x00b")]), "x" * (2 * 1024 * 1024 + 1)):
            with self.subTest(size=len(data)), self.assertRaises(ValidationError):
                parse_csv("results", data)

    def test_api_owner_isolation_history_and_receipt_recovery(self):
        client = APIClient()
        client.force_authenticate(self.hod)
        response = client.post("/api/imports/previews/", {"kind": "results", "request_id": str(uuid.uuid4()),
            "filename": "source.csv", "csv_text": csv_text(RESULT_COLUMNS, [self.result_row()])}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        batch_id = response.data["id"]
        commit = client.post(f"/api/imports/{batch_id}/commit/", {"preview_digest": response.data["preview_digest"], "correction_approvals": []}, format="json")
        self.assertEqual(commit.status_code, 201, commit.data)
        saved = client.get(f"/api/imports/{batch_id}/")
        self.assertEqual(saved.data["receipt"]["created_results"], 1)
        self.assertEqual(client.get("/api/imports/").data["count"], 1)
        client.force_authenticate(self.staff)
        self.assertEqual(client.get(f"/api/imports/{batch_id}/").status_code, 404)
        self.assertEqual(client.get("/api/imports/").data["count"], 0)

    def test_anonymous_and_students_cannot_import(self):
        client = APIClient()
        self.assertEqual(client.get("/api/imports/").status_code, 403)
        client.force_authenticate(get_user_model().objects.create_user(username="plain-student"))
        self.assertEqual(client.get("/api/imports/").status_code, 403)

    def test_history_kind_filter_is_owner_scoped_before_pagination(self):
        for _ in range(21):
            self.preview()
        self.preview("roster", [self.roster_row()])
        for _ in range(3):
            self.preview(user=self.staff)
        client = APIClient()
        client.force_authenticate(self.hod)
        response = client.get("/api/imports/?kind=results")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertTrue(all(row["kind"] == "results" for row in response.data["results"]))
        self.assertIn("kind=results", response.data["next"])
        following = client.get(response.data["next"])
        self.assertEqual(len(following.data["results"]), 1)
        self.assertEqual(client.get("/api/imports/?kind=roster").data["count"], 1)
        self.assertEqual(client.get("/api/imports/").data["count"], 22)
        client.force_authenticate(self.staff)
        self.assertEqual(client.get("/api/imports/?kind=results").data["count"], 3)
        self.assertEqual(client.get("/api/imports/?kind=roster").data["count"], 0)

    def test_history_rejects_invalid_kind_filter(self):
        client = APIClient()
        client.force_authenticate(self.hod)
        for kind in ("students", "", "RESULTS"):
            with self.subTest(kind=kind):
                response = client.get("/api/imports/", {"kind": kind})
                self.assertEqual(response.status_code, 400)
                self.assertIn("kind", response.data)
