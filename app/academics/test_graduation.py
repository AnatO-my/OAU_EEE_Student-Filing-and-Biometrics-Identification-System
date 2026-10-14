from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from students.models import Student
from . import test_api as fixtures
from .models import Course, CourseOffering, CourseRequirement, GraduationReview, Result
from .services import create_result, update_result_score, verify_result


class GraduationWorkflowTests(APITestCase):
    setUp = fixtures.ResultCreateAPITests.setUp

    def prepare(self, student=None, score="40"):
        student = student or self.student
        result = create_result(user=self.hod, student=student, offering=self.offering, score=Decimal(score))
        verify_result(user=self.hod, result=result, expected_score=Decimal(score))
        CourseRequirement.objects.create(student=student, offering=self.offering, recorded_by=self.hod)
        return result

    def review_url(self, student=None):
        return reverse("graduation-review", kwargs={"student_id": (student or self.student).pk})

    def approve(self, student=None, digest=None):
        self.client.force_authenticate(self.hod)
        if digest is None:
            response = self.client.get(self.review_url(student))
            self.assertEqual(response.status_code, 200)
            digest = response.data["history_digest"]
        return self.client.post(self.review_url(student), {"notes": "Required history and other requirements reviewed.",
            "expected_digest": digest, "history_complete": True, "other_requirements_satisfied": True}, format="json")

    def graduate(self, student=None):
        self.client.force_authenticate(self.hod)
        return self.client.patch(reverse("student-detail", kwargs={"student_id": (student or self.student).pk}),
            {"academic_status": "graduated"}, format="json")

    def test_exactly_one_qualifies_after_hod_review(self):
        self.prepare()
        self.assertEqual(self.graduate().status_code, 400)
        self.assertEqual(self.approve().status_code, 200)
        self.assertEqual(self.graduate().status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.academic_status, "graduated")
        self.assertEqual(self.student.current_level, 300)
        self.assertTrue(self.student.is_active)

    def test_point_995_never_rounds_into_eligibility(self):
        Result.objects.create(student=self.student, offering=self.offering, score=Decimal("40"),
            credit_units=199, is_verified=True)
        Result.objects.create(student=self.student, offering=self.offering, attempt_number=2,
            score=Decimal("0"), credit_units=1, is_verified=True)
        CourseRequirement.objects.create(student=self.student, offering=self.offering, recorded_by=self.hod)
        self.client.force_authenticate(self.hod)
        self.assertEqual(self.client.get(self.review_url()).status_code, 400)
        self.assertEqual(self.graduate().status_code, 400)

    def test_missing_requirement_result_blocks_review(self):
        self.prepare()
        course = Course.objects.create(code="EEE302", title="Another required course")
        offering = CourseOffering.objects.create(course=course, academic_session=self.offering.academic_session,
            semester="rain", level=300, credit_units=3)
        requirement = CourseRequirement.objects.create(student=self.student, offering=offering, recorded_by=self.hod)
        self.client.force_authenticate(self.hod)
        self.assertEqual(self.client.get(self.review_url()).status_code, 400)
        detail = reverse("course-requirement-detail", kwargs={"student_id": self.student.pk, "requirement_id": requirement.pk})
        self.assertEqual(self.client.patch(detail, {"resolution": "exemption"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(detail, {"resolution": "exemption", "reason": "HOD-reviewed exemption reference EX-1"}, format="json").status_code, 200)
        self.assertEqual(self.approve().status_code, 200)

    def test_no_requirement_manifest_blocks_review(self):
        result = self.prepare()
        self.student.course_requirements.all().delete()
        self.client.force_authenticate(self.hod)
        self.assertEqual(self.client.get(self.review_url()).status_code, 400)

    def test_changed_history_rejects_stale_preview_and_approval(self):
        result = self.prepare()
        self.client.force_authenticate(self.hod)
        digest = self.client.get(self.review_url()).data["history_digest"]
        update_result_score(user=self.hod, result=result, score=Decimal("50"))
        verify_result(user=self.hod, result=result, expected_score=Decimal("50"))
        self.assertEqual(self.approve(digest=digest).status_code, 400)
        self.assertFalse(GraduationReview.objects.exists())
        self.assertEqual(self.approve().status_code, 200)
        update_result_score(user=self.hod, result=result, score=Decimal("60"))
        verify_result(user=self.hod, result=result, expected_score=Decimal("60"))
        self.assertEqual(self.graduate().status_code, 400)
        self.assertEqual(self.approve().status_code, 200)
        self.assertEqual(self.graduate().status_code, 200)

    def test_hod_must_confirm_other_requirements(self):
        self.prepare()
        self.client.force_authenticate(self.hod)
        digest = self.client.get(self.review_url()).data["history_digest"]
        response = self.client.post(self.review_url(), {"expected_digest": digest, "notes": "Not finished",
            "history_complete": True, "other_requirements_satisfied": False}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(GraduationReview.objects.exists())

    def test_graduation_review_is_hod_only(self):
        self.prepare()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.review_url()).status_code, 403)
        self.assertEqual(self.client.post(self.review_url(), {}, format="json").status_code, 403)

    def test_bulk_graduation_is_all_or_nothing(self):
        self.prepare()
        self.assertEqual(self.approve().status_code, 200)
        other = Student.objects.create(identifier_type="matriculation", identifier_value="000999",
            full_name="Other student", phone_number="08000000000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        self.prepare(other)
        payload = {"student_ids": [str(self.student.pk), str(other.pk)],
            "expected_status": "undergraduate", "academic_status": "graduated"}
        url = reverse("bulk-student-status-change")
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        self.assertEqual(Student.objects.filter(academic_status="graduated").count(), 0)
        self.assertEqual(self.approve(other).status_code, 200)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        self.assertEqual(Student.objects.filter(academic_status="graduated").count(), 2)

    def test_graduated_history_requires_explicit_hod_reopening(self):
        result = self.prepare()
        self.approve()
        self.graduate()
        detail = reverse("result-score-update", kwargs={"result_id": result.pk})
        self.assertEqual(self.client.patch(detail, {"score": "50"}, format="json").status_code, 400)
        student_url = reverse("student-detail", kwargs={"student_id": self.student.pk})
        self.assertEqual(self.client.patch(student_url, {"academic_status": "undergraduate"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(detail, {"score": "50"}, format="json").status_code, 200)

    def test_profile_change_cannot_bypass_review_during_graduation(self):
        self.prepare()
        self.approve()
        response = self.client.patch(reverse("student-detail", kwargs={"student_id": self.student.pk}),
            {"current_level": 400, "academic_status": "graduated"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_level, 300)
        self.assertEqual(self.student.academic_status, "undergraduate")

    def test_admin_cannot_bypass_graduation_or_account_linking(self):
        self.client.force_login(self.hod)
        response = self.client.post(f"/admin/students/student/{self.student.pk}/change/", {
            "identifier_type": self.student.identifier_type,
            "identifier_value": self.student.identifier_value,
            "full_name": self.student.full_name, "phone_number": self.student.phone_number,
            "admission_year": self.student.admission_year,
            "mode_of_admission": self.student.mode_of_admission,
            "current_level": self.student.current_level, "is_active": "on",
            "academic_status": "graduated", "user": self.hod.pk, "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.academic_status, "undergraduate")
        self.assertIsNone(self.student.user_id)

    def test_cgpa_reports_current_review(self):
        self.prepare()
        self.approve()
        response = self.client.get(reverse("student-cgpa", kwargs={"student_id": self.student.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["history_completeness"], "hod_reviewed")
