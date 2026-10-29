"""Synthetic source-performance evidence, acceptance and permission regressions."""
from copy import deepcopy
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from academics.models import AcademicSession, CourseOffering, Result
from .models import ImportBatch, SourcePerformance
from .performance import compare, metric
from .preparation import prepare_source
from .services import ImportConflict, create_preview, public_batch
from .test_imports import ImportFixture
from .test_preparation import nested_csv, source_record


class SourcePerformanceTests(ImportFixture, TestCase):
    def prepared(self, **values):
        record = {**source_record(), "matric_number": "000123", **values}
        return prepare_source(nested_csv(record), "synthetic_students.csv", attempt_number=1)

    def stage(self, prepared=None, request_id=None, user=None):
        prepared = prepared or self.prepared(current_gpa="4.20", previous_gpa="1.10", cgpa="4.30")
        return create_preview(user=user or self.hod, kind="results", request_id=request_id or uuid.uuid4(),
            filename=prepared["filename"], csv_text=prepared["csv_text"], source_context=deepcopy(prepared["source_context"]))[0]

    def test_discrepancy_nonblocking_persists_on_commit_reload_and_retry(self):
        batch = self.stage()
        comparison = public_batch(batch)["source_performance"][0]["comparison"]
        self.assertEqual(comparison["gpa"]["status"], "different")
        self.assertEqual(comparison["gpa"]["calculated"], "5.00")
        self.assertEqual(comparison["previous_reported_gpa"], "1.10")
        self.assertFalse(comparison["blocking"])
        self.assertTrue(public_batch(batch)["can_commit"])
        committed, _ = self.commit(batch)
        evidence = SourcePerformance.objects.get(batch=batch)
        self.assertEqual(evidence.review_status, "unresolved")
        self.assertEqual(evidence.source["current_gpa"], "4.20")
        self.assertEqual(evidence.source["semester_remark"], "Passed")
        self.assertEqual(evidence.source["current_courses"][0]["raw_result"], "76A")
        self.assertFalse(Result.objects.get(student=self.student).is_verified)
        self.assertEqual(public_batch(ImportBatch.objects.get(pk=batch.pk))["source_performance"][0]["comparison"], comparison)
        self.commit(committed)
        self.assertEqual(SourcePerformance.objects.count(), 1)

    def test_matching_missing_and_provisional_comparability_are_distinct(self):
        matched = self.stage(self.prepared())
        self.assertEqual(matched.preview["source_performance"][0]["comparison"]["gpa"]["status"], "matching")
        missing = self.stage(self.prepared(current_gpa="", previous_gpa="", cgpa=""))
        comparison = missing.preview["source_performance"][0]["comparison"]
        self.assertEqual(comparison["gpa"]["status"], "not_reported")
        self.assertIsNone(comparison["previous_reported_gpa"])
        self.assertEqual(metric("3.50", None)["status"], "not_comparable")
        self.assertEqual(metric("3.345", "3.35")["status"], "matching")

    def test_gpa_api_retains_both_figures_and_protects_student_scope(self):
        batch = self.stage()
        self.commit(batch)
        Result.objects.filter(student=self.student).update(is_verified=True)
        client = APIClient()
        client.force_authenticate(self.hod)
        url = f"/api/students/{self.student.pk}/gpa/?academic_session=2026/2027&semester=harmattan"
        response = client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data["gpa"]), Decimal("5"))
        report = response.data["source_reports"][0]
        self.assertEqual(report["comparison"]["gpa"]["reported"], "4.20")
        self.assertEqual(report["comparison"]["gpa"]["status"], "different")
        self.assertEqual(report["review_status"], "unresolved")
        self.assertNotIn("inputs", report["comparison_at_import"])
        student_user = get_user_model().objects.create_user(username="source-owner")
        self.student.user = student_user
        self.student.save()
        client.force_authenticate(student_user)
        self.assertEqual(client.get('/api/me/gpa/?academic_session=2026/2027&semester=harmattan').status_code, 200)
        stranger = get_user_model().objects.create_user(username="source-stranger")
        client.force_authenticate(stranger)
        self.assertEqual(client.get('/api/me/cgpa/').status_code, 404)
        self.assertIn(client.get(url).status_code, (403, 404))

    def test_source_context_bound_to_csv_period_idempotency_and_hash(self):
        prepared = self.prepared()
        request_id = uuid.uuid4()
        batch = self.stage(prepared, request_id)
        self.assertEqual(self.stage(prepared, request_id).pk, batch.pk)
        changed = deepcopy(prepared)
        changed["source_context"]["records"][0]["cgpa"] = "2.0"
        with self.assertRaises(ImportConflict):
            self.stage(changed, request_id)
        wrong_period = deepcopy(prepared)
        wrong_period["source_context"]["records"][0]["current_semester"] = "rain"
        with self.assertRaises(ValidationError):
            self.stage(wrong_period)
        wrong_hash = deepcopy(prepared)
        wrong_hash["source_context"]["csv_sha256"] = "a" * 64
        with self.assertRaises(ValidationError):
            self.stage(wrong_hash)

    def test_discrepancy_does_not_bypass_unknown_student_or_invalid_score(self):
        prepared = self.prepared(matric_number="999123")
        batch = self.stage(prepared)
        self.assertFalse(public_batch(batch)["can_commit"])
        with self.assertRaises(ImportConflict):
            self.commit(batch)
        self.assertFalse(SourcePerformance.objects.exists())
        invalid = self.preview(rows=[self.result_row(score="101")])
        self.assertEqual(invalid.preview["summary"]["blocked"], 1)

    def test_correction_approval_and_stale_history_remain_required(self):
        Result.objects.create(student=self.student, offering=self.offering, credit_units=3, grading_scale=self.offering.grading_scale, score=60, is_verified=True)
        batch = self.stage()
        with self.assertRaises(ValidationError):
            self.commit(batch)
        self.commit(batch, approvals=[{"row_number": 2, "reason": "Reviewed original corrected score."}])
        self.assertEqual(SourcePerformance.objects.count(), 1)
        batch = self.stage()
        Result.objects.filter(student=self.student).update(is_verified=True)
        with self.assertRaises(ImportConflict):
            self.commit(batch)

    def test_corresponding_period_uses_all_attempts_and_excludes_future_results(self):
        Result.objects.create(student=self.student, offering=self.offering, credit_units=3, grading_scale=self.offering.grading_scale, score=30, is_verified=True)
        Result.objects.create(student=self.student, offering=self.offering, credit_units=3, grading_scale=self.offering.grading_scale, score=76, attempt_number=2, is_verified=True)
        later = CourseOffering.objects.create(course=self.course, academic_session=self.session,
            semester="rain", level=100, credit_units=3, grading_scale=self.offering.grading_scale)
        Result.objects.create(student=self.student, offering=later, credit_units=3, grading_scale=self.offering.grading_scale, score=30, is_verified=True)
        comparison = compare(self.student, "2026/2027", "harmattan", {"current_gpa": "2.50", "cgpa": "2.50", "previous_gpa": "1.0"})
        self.assertEqual(comparison["cgpa"]["calculated"], "2.50")
        self.assertEqual(comparison["gpa"]["status"], "matching")
        self.assertEqual(comparison["history_completeness"], "not_established")

    def test_canonical_csv_without_reported_context_keeps_existing_contract(self):
        batch = self.preview()
        self.commit(batch)
        self.assertEqual(public_batch(batch)["source_performance"], [])
        self.assertFalse(SourcePerformance.objects.exists())

    def test_malformed_or_nonfinite_source_context_fails_without_writes(self):
        for field, value in (("current_gpa", "NaN"), ("current_semester", []), ("source_page", {})):
            with self.subTest(field=field):
                prepared = self.prepared()
                prepared["source_context"]["records"][0][field] = value
                with self.assertRaises(ValidationError):
                    self.stage(prepared)
        self.assertFalse(ImportBatch.objects.exists())

    def test_later_matching_calculation_does_not_erase_import_discrepancy(self):
        batch = self.stage(self.prepared(current_gpa="4.00", cgpa="4.00"))
        self.commit(batch)
        Result.objects.filter(student=self.student).update(score=68, is_verified=True)
        from .performance import source_reports
        report, = source_reports(self.student, self.session, "harmattan")
        self.assertEqual(report["comparison"]["gpa"]["status"], "matching")
        self.assertEqual(report["comparison_at_import"]["gpa"]["status"], "different")
        self.assertEqual(report["review_status"], "unresolved")

    def test_source_ng_cannot_be_relabelled_as_an_accepted_numeric_result(self):
        prepared = self.prepared()
        course = prepared["source_context"]["records"][0]["current_courses"][0]
        course.update(grade="NG", raw_result="0NG", score=0)
        with self.assertRaises(ValidationError):
            self.stage(prepared)
