from copy import deepcopy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import AdviserAssignment
from . import test_api as fixtures
from .calculations import calculate_student_cgpa
from .grading import INITIAL_BANDS, grade_point_for_score, validate_bands
from .models import Course, CourseOffering, GradingScale, Result
from .services import (
    assign_offering_scale, create_result, update_result_score, verify_result,
    create_grading_scale, publish_grading_scale, update_grading_scale,
)


# Verify grading-version validation, publication, history preservation, and HOD-only management.
class GradingVersionTests(APITestCase):
    setUp = fixtures.ResultCreateAPITests.setUp

    # Create an unpublished scale using a copy of the default bands unless overridden.
    def draft(self, name="Next grading version", bands=None):
        return create_grading_scale(user=self.hod, validated_data={
            "name": name, "bands": deepcopy(INITIAL_BANDS) if bands is None else bands,
        })

    # Reject scale definitions with overlaps, gaps, or incomplete coverage.
    def test_bands_reject_overlaps_gaps_and_incomplete_coverage(self):
        for change in ("overlap", "gap", "start", "end"):
            bands = deepcopy(INITIAL_BANDS)
            if change == "overlap": bands[1]["minimum"] = "39"
            if change == "gap": bands[1]["minimum"] = "41"
            if change == "start": bands[0]["minimum"] = "1"
            if change == "end": bands[-1]["maximum"] = "99"
            with self.subTest(change=change), self.assertRaises(ValidationError):
                validate_bands(bands)

    # Reject non-finite, out-of-range, fractional, or over-precise band values.
    def test_invalid_numeric_band_values_are_rejected(self):
        for key, value in (("minimum", "NaN"), ("maximum", "Infinity"),
                           ("grade_point", "6"), ("grade_point", "2.5"),
                           ("minimum", "0.001")):
            bands = deepcopy(INITIAL_BANDS)
            bands[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                validate_bands(bands)

    # Verify boundary scores, including 100, map to exactly one published band.
    def test_shared_boundaries_and_100_have_one_owner(self):
        scale = GradingScale.objects.get(name="Initial five-point scale")
        for score, expected in (("39.99", "0"), ("40", "1"), ("70", "5"), ("100", "5")):
            with self.subTest(score=score):
                self.assertEqual(grade_point_for_score(Decimal(score), grading_scale=scale), Decimal(expected))

    # Allow draft edits but lock the version against service and direct-model changes after publication.
    def test_draft_edits_then_publication_locks_version(self):
        scale = self.draft()
        scale = update_grading_scale(user=self.hod, scale=scale, validated_data={"name": "Reviewed version"})
        scale = publish_grading_scale(user=self.hod, scale=scale)
        with self.assertRaises(ValidationError):
            update_grading_scale(user=self.hod, scale=scale, validated_data={"name": "Changed"})
        scale.name = "Changed directly"
        with self.assertRaises(ValidationError):
            scale.save()
        scale.refresh_from_db()
        self.assertEqual(scale.name, "Reviewed version")

    # Preserve historical result grading while applying a new published scale to later results.
    def test_versions_preserve_old_results_and_weight_new_results(self):
        old = create_result(user=self.hod, student=self.student, offering=self.offering, score=Decimal("68"))
        verify_result(user=self.hod, result=old, expected_score=Decimal("68"))
        bands = deepcopy(INITIAL_BANDS)
        bands[-2]["maximum"] = "65"
        bands[-1]["minimum"] = "65"
        scale = publish_grading_scale(user=self.hod, scale=self.draft(bands=bands))
        course = Course.objects.create(code="EEE302", title="Second example")
        offering = CourseOffering.objects.create(course=course,
            academic_session=self.offering.academic_session, semester="rain",
            level=300, credit_units=3, grading_scale=scale)
        new = create_result(user=self.hod, student=self.student, offering=offering, score=Decimal("68"))
        verify_result(user=self.hod, result=new, expected_score=Decimal("68"))
        old.refresh_from_db()
        self.assertNotEqual(old.grading_scale_id, new.grading_scale_id)
        self.assertEqual(grade_point_for_score(old.score, grading_scale=old.grading_scale), Decimal("4"))
        self.assertEqual(calculate_student_cgpa(student=self.student), Decimal("4.5"))

    # Prevent switching an offering's grading version after results have been recorded.
    def test_used_offering_cannot_switch_version(self):
        create_result(user=self.hod, student=self.student, offering=self.offering, score=Decimal("68"))
        scale = publish_grading_scale(user=self.hod, scale=self.draft())
        with self.assertRaises(ValidationError):
            assign_offering_scale(user=self.hod, offering=self.offering, scale=scale)
        self.offering.refresh_from_db()
        self.assertNotEqual(self.offering.grading_scale_id, scale.pk)

    # Allow an unused offering to adopt a published scale for its new results.
    def test_unused_offering_can_select_published_version(self):
        scale = publish_grading_scale(user=self.hod, scale=self.draft())
        offering = assign_offering_scale(user=self.hod, offering=self.offering, scale=scale)
        result = create_result(user=self.hod, student=self.student, offering=offering)
        self.assertEqual(result.grading_scale_id, scale.pk)

    # Refuse result creation when its offering references an unpublished scale.
    def test_draft_scale_cannot_be_used_by_results(self):
        self.offering.grading_scale = self.draft()
        self.offering.save(update_fields=["grading_scale"])
        with self.assertRaises(ValidationError):
            create_result(user=self.hod, student=self.student, offering=self.offering, score=Decimal("68"))
        self.assertFalse(Result.objects.exists())

    # Exercise the HOD API lifecycle for draft creation, validation, publication, and retrieval.
    def test_grading_api_lifecycle_and_invalid_edits(self):
        self.client.force_authenticate(self.hod)
        response = self.client.post(reverse("grading-scale-list"),
            {"name": "API version", "bands": INITIAL_BANDS}, format="json")
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        detail = reverse("grading-scale-detail", kwargs={"scale_id": pk})
        bands = deepcopy(INITIAL_BANDS)
        bands[1]["minimum"] = "39"
        self.assertEqual(self.client.patch(detail, {"bands": bands}, format="json").status_code, 400)
        published = self.client.post(reverse("grading-scale-publish", kwargs={"scale_id": pk}), {}, format="json")
        self.assertEqual(published.status_code, 200)
        self.assertTrue(published.data["is_published"])
        self.assertEqual(self.client.patch(detail, {"name": "Changed"}, format="json").status_code, 400)
        self.assertEqual(self.client.get(detail).status_code, 200)

    # Prevent advisers from managing grading scales even when they have result permissions.
    def test_adviser_cannot_manage_grading_even_with_result_permissions(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(reverse("grading-scale-list"),
            {"name": "Forbidden", "bands": INITIAL_BANDS}, format="json").status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.draft_for_staff()

    # Confirm the service independently rejects a staff member's grading-scale request.
    def draft_for_staff(self):
        return create_grading_scale(user=self.staff, validated_data={"name": "Forbidden", "bands": INITIAL_BANDS})


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
# Verify adviser result access is permission-specific and bound to a current assignment.
class AdviserResultPermissionTests(APITestCase):
    setUp = fixtures.ResultCreateAPITests.setUp

    # Grant named permissions and refresh the user to clear Django's cached permission set.
    def grant(self, *codes):
        for code in codes:
            app, name = code.split(".")
            self.staff.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=name))
        # A new instance avoids Django's per-instance permission cache.
        self.staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(self.staff)

    # Create an adviser assignment for the requested session, level, and active state.
    def assign(self, level=300, session="2026/2027", active=True):
        return AdviserAssignment.objects.create(staff=self.staff, academic_session=session, level=level, is_active=active)

    # Create a result under HOD authority for adviser-access checks.
    def result(self):
        return create_result(user=self.hod, student=self.student, offering=self.offering, score=Decimal("68"))

    # Grant the two permissions required to read academic results.
    def grant_read(self):
        self.grant("students.view_student", "academics.view_result")

    # Require both read permission and a matching current-session adviser assignment.
    def test_read_requires_permission_and_current_assignment(self):
        result = self.result()
        self.assign()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.grant_read()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [result.pk])
        self.assertEqual(self.client.get(reverse("student-cgpa", kwargs={"student_id": self.student.pk})).status_code, 400)

    # Enforce separate permissions for adding, changing, and verifying results.
    def test_add_change_and_verify_are_separate_permissions(self):
        self.assign()
        self.grant_read()
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)
        self.grant("academics.add_result")
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        detail = reverse("result-score-update", kwargs={"result_id": pk})
        verify = reverse("result-verify", kwargs={"result_id": pk})
        self.assertEqual(self.client.patch(detail, {"score": "75"}, format="json").status_code, 403)
        self.grant("academics.change_result")
        self.assertEqual(self.client.patch(detail, {"score": "75"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(verify, {"expected_score": "75"}, format="json").status_code, 403)
        self.grant("academics.verify_result")
        self.assertEqual(self.client.post(verify, {"expected_score": "75"}, format="json").status_code, 200)
        cgpa = self.client.get(reverse("student-cgpa", kwargs={"student_id": self.student.pk}))
        self.assertEqual(cgpa.status_code, 200)
        self.assertEqual(Decimal(cgpa.data["cgpa"]), Decimal("5"))

    # Hide and reject operations on students outside the adviser's assigned level.
    def test_foreign_level_cannot_be_read_or_modified(self):
        result = self.result()
        self.assign(level=200)
        self.grant_read()
        self.grant("academics.add_result", "academics.change_result", "academics.verify_result")
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        detail = reverse("result-score-update", kwargs={"result_id": result.pk})
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.patch(detail, {"score": "75"}, format="json").status_code, 404)
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 400)
        with self.assertRaises(PermissionDenied):
            update_result_score(user=self.staff, result=result, score=Decimal("75"))
        with self.assertRaises(PermissionDenied):
            verify_result(user=self.staff, result=result, expected_score=Decimal("68"))
        with self.assertRaises(PermissionDenied):
            create_result(user=self.staff, student=self.student, offering=self.offering, attempt_number=2)

    # Deny access for assignments from another session or assignments that are inactive.
    def test_old_or_revoked_assignment_grants_no_access(self):
        self.result()
        self.assign(session="2025/2026")
        self.assign(active=False)
        self.grant_read()
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    # Revoke access when a student's current level no longer matches the assignment.
    def test_student_level_change_revokes_previous_adviser_access(self):
        result = self.result()
        self.assign()
        self.grant_read()
        self.student.current_level = 400
        self.student.save(update_fields=["current_level"])
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(reverse("result-score-update", kwargs={"result_id": result.pk})).status_code, 404)

    @override_settings(CURRENT_ACADEMIC_SESSION="")
    # Fail closed when no current academic session is configured.
    def test_missing_current_session_fails_closed(self):
        self.result()
        self.assign()
        self.grant_read()
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    # Refuse service operations when a previously authorized staff account is inactive.
    def test_inactive_staff_service_access_is_denied(self):
        self.assign()
        self.grant_read()
        self.grant("academics.add_result")
        self.staff.is_active = False
        with self.assertRaises(PermissionDenied):
            create_result(user=self.staff, student=self.student, offering=self.offering)

    # Apply the current student assignment to historical results from earlier sessions.
    def test_historical_results_follow_current_student_assignment(self):
        self.offering.academic_session.name = "2025/2026"
        self.offering.academic_session.save(update_fields=["name"])
        result = self.result()
        self.assign()
        self.grant_read()
        response = self.client.get(reverse("result-score-update", kwargs={"result_id": result.pk}))
        self.assertEqual(response.status_code, 200)

    # Require student-read permission in addition to academic-result permission.
    def test_result_permission_without_student_read_permission_is_denied(self):
        self.assign()
        self.grant("academics.view_result", "academics.add_result")
        self.assertEqual(self.client.get(self.url).status_code, 403)
