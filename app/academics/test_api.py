from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from students.models import Student

from .models import AcademicSession, Course, CourseOffering, Result


class ResultCreateAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.hod = User.objects.create_user(
            username="hod",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username="staff",
            is_staff=True,
        )
        self.student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="001234",
            full_name="Example Student",
            phone_number="08000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        session = AcademicSession.objects.create(name="2026/2027")
        course = Course.objects.create(
            code="EEE301",
            title="Example Course",
        )
        self.offering = CourseOffering.objects.create(
            course=course,
            academic_session=session,
            semester=CourseOffering.Semester.HARMATTAN,
            level=300,
            credit_units=3,
        )
        self.url = reverse("result-create")
        self.payload = {
            "student_id": str(self.student.pk),
            "offering_id": self.offering.pk,
            "attempt_number": 1,
            "score": "68.00",
        }

    def test_hod_can_create_result(self):
        self.client.force_authenticate(self.hod)

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        result = Result.objects.get()
        self.assertEqual(result.student_id, self.student.pk)
        self.assertEqual(result.offering_id, self.offering.pk)
        self.assertEqual(result.score, Decimal("68.00"))
        self.assertEqual(result.credit_units, 3)
        self.assertFalse(result.is_verified)

    def test_ordinary_staff_cannot_create_result(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Result.objects.exists())

    def test_duplicate_attempt_returns_validation_error(self):
        self.client.force_authenticate(self.hod)
        first = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(first.status_code, 201)

        response = self.client.post(
            self.url,
            {**self.payload, "score": "75.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Result.objects.count(), 1)
        self.assertEqual(
            Result.objects.get().score,
            Decimal("68.00"),
        )

    def test_invalid_score_creates_nothing(self):
        self.client.force_authenticate(self.hod)

        response = self.client.post(
            self.url,
            {**self.payload, "score": "100.01"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Result.objects.exists())

    def make_verified_result(self):
        return Result.objects.create(
            student=self.student,
            offering=self.offering,
            attempt_number=1,
            score=Decimal("68.00"),
            credit_units=3,
            is_verified=True,
        )

    def test_hod_correction_resets_verification(self):
        result = self.make_verified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.patch(
            reverse(
                "result-score-update",
                kwargs={"result_id": result.pk},
            ),
            {"score": "75.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("75.00"))
        self.assertFalse(result.is_verified)
        self.assertEqual(result.credit_units, 3)

    def test_staff_cannot_correct_result(self):
        result = self.make_verified_result()
        self.client.force_authenticate(self.staff)

        response = self.client.patch(
            reverse(
                "result-score-update",
                kwargs={"result_id": result.pk},
            ),
            {"score": "75.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("68.00"))
        self.assertTrue(result.is_verified)

    def test_correction_requires_explicit_score(self):
        result = self.make_verified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.patch(
            reverse(
                "result-score-update",
                kwargs={"result_id": result.pk},
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("68.00"))
        self.assertTrue(result.is_verified)

    def test_null_score_clears_score_and_verification(self):
        result = self.make_verified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.patch(
            reverse(
                "result-score-update",
                kwargs={"result_id": result.pk},
            ),
            {"score": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        result.refresh_from_db()
        self.assertIsNone(result.score)
        self.assertFalse(result.is_verified)

    def make_unverified_result(self, score=Decimal("68.00")):
        return Result.objects.create(
            student=self.student,
            offering=self.offering,
            attempt_number=1,
            score=score,
            credit_units=3,
            is_verified=False,
        )

    def test_hod_can_verify_result(self):
        result = self.make_unverified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.post(
            reverse(
                "result-verify",
                kwargs={"result_id": result.pk},
            ),
            {"expected_score": "68.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        result.refresh_from_db()
        self.assertTrue(result.is_verified)

    def test_staff_cannot_verify_result(self):
        result = self.make_unverified_result()
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            reverse(
                "result-verify",
                kwargs={"result_id": result.pk},
            ),
            {"expected_score": "68.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        result.refresh_from_db()
        self.assertFalse(result.is_verified)

    def test_different_reviewed_score_is_rejected(self):
        result = self.make_unverified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.post(
            reverse(
                "result-verify",
                kwargs={"result_id": result.pk},
            ),
            {"expected_score": "75.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        result.refresh_from_db()
        self.assertFalse(result.is_verified)
        self.assertEqual(result.score, Decimal("68.00"))

    def test_missing_saved_score_cannot_be_verified(self):
        result = self.make_unverified_result(score=None)
        self.client.force_authenticate(self.hod)

        response = self.client.post(
            reverse(
                "result-verify",
                kwargs={"result_id": result.pk},
            ),
            {"expected_score": "68.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        result.refresh_from_db()
        self.assertFalse(result.is_verified)

    def test_hod_can_list_results_for_review(self):
        result = self.make_unverified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            result.pk,
        )
        self.assertFalse(response.data["results"][0]["is_verified"])

    def test_staff_cannot_list_results(self):
        self.make_unverified_result()
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_result_list_is_paginated(self):
        Result.objects.bulk_create(
            [
                Result(
                    student=self.student,
                    offering=self.offering,
                    attempt_number=attempt,
                    score=Decimal("68.00"),
                    credit_units=3,
                    is_verified=False,
                )
                for attempt in range(1, 22)
            ]
        )
        self.client.force_authenticate(self.hod)

        first_page = self.client.get(self.url)
        second_page = self.client.get(
            self.url,
            {"page": 2},
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.data["count"], 21)
        self.assertEqual(
            len(first_page.data["results"]),
            20,
        )
        self.assertIsNotNone(first_page.data["next"])

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(
            len(second_page.data["results"]),
            1,
        )

        first_ids = {item["id"] for item in first_page.data["results"]}
        second_ids = {item["id"] for item in second_page.data["results"]}
        self.assertTrue(first_ids.isdisjoint(second_ids))

    def test_verification_filter_selects_matching_results(self):
        unverified = self.make_unverified_result()
        verified = Result.objects.create(
            student=self.student,
            offering=self.offering,
            attempt_number=2,
            score=Decimal("75.00"),
            credit_units=3,
            is_verified=True,
        )
        self.client.force_authenticate(self.hod)

        for value, expected in (
            ("false", unverified),
            ("true", verified),
        ):
            with self.subTest(is_verified=value):
                response = self.client.get(
                    self.url,
                    {"is_verified": value},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(
                    response.data["results"][0]["id"],
                    expected.pk,
                )

    def test_session_and_semester_filters_combine(self):
        expected = self.make_unverified_result()

        other_session = AcademicSession.objects.create(name="2025/2026")

        for session, semester in (
            (
                other_session,
                CourseOffering.Semester.HARMATTAN,
            ),
            (
                self.offering.academic_session,
                CourseOffering.Semester.RAIN,
            ),
        ):
            offering = CourseOffering.objects.create(
                course=self.offering.course,
                academic_session=session,
                semester=semester,
                level=300,
                credit_units=3,
            )
            Result.objects.create(
                student=self.student,
                offering=offering,
                score=Decimal("68.00"),
                credit_units=3,
            )

        self.client.force_authenticate(self.hod)
        response = self.client.get(
            self.url,
            {
                "academic_session": "2026/2027",
                "semester": "harmattan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            expected.pk,
        )

    def test_student_filter_excludes_other_students(self):
        expected = self.make_unverified_result()
        other_student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="009999",
            full_name="Another Student",
            phone_number="08000000001",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        Result.objects.create(
            student=other_student,
            offering=self.offering,
            score=Decimal("75.00"),
            credit_units=3,
        )

        self.client.force_authenticate(self.hod)
        response = self.client.get(
            self.url,
            {"student_id": str(self.student.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            expected.pk,
        )

    def test_invalid_filters_return_validation_errors(self):
        self.client.force_authenticate(self.hod)

        for filters in (
            {"student_id": "invalid"},
            {"academic_session": "2026"},
            {"academic_session": "2026/2028"},
            {"semester": "invalid"},
            {"is_verified": "invalid"},
        ):
            with self.subTest(filters=filters):
                response = self.client.get(
                    self.url,
                    filters,
                )
                self.assertEqual(response.status_code, 400)
    def test_hod_can_retrieve_one_result(self):
        result = self.make_unverified_result()
        self.client.force_authenticate(self.hod)

        response = self.client.get(
            reverse(
                "result-score-update",
                kwargs={"result_id": result.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], result.pk)
        self.assertEqual(response.data["credit_units"], 3)
        self.assertFalse(response.data["is_verified"])

    def test_staff_cannot_retrieve_result_detail(self):
        result = self.make_unverified_result()
        self.client.force_authenticate(self.staff)

        response = self.client.get(
            reverse(
                "result-score-update",
                kwargs={"result_id": result.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_missing_result_returns_404_for_hod(self):
        result = self.make_unverified_result()
        missing_id = result.pk
        result.delete()

        self.client.force_authenticate(self.hod)
        response = self.client.get(
            reverse(
                "result-score-update",
                kwargs={"result_id": missing_id},
            )
        )

        self.assertEqual(response.status_code, 404)

class AcademicSummaryAndAccessTests(APITestCase):
    setUp = ResultCreateAPITests.setUp
    make_unverified_result = ResultCreateAPITests.make_unverified_result
    make_verified_result = ResultCreateAPITests.make_verified_result

    def student_login(self):
        user = get_user_model().objects.create_user(username="student-account")
        self.student.user = user
        self.student.save(update_fields=["user"])
        self.client.force_authenticate(user)
        return user

    def test_hod_gpa_and_cgpa_count_both_attempts(self):
        self.make_verified_result()
        Result.objects.create(student=self.student, offering=self.offering,
                              attempt_number=2, score=Decimal("30"),
                              credit_units=3, is_verified=True)
        self.client.force_authenticate(self.hod)
        gpa = self.client.get(reverse("student-gpa", kwargs={"student_id": self.student.pk}),
                              {"academic_session": "2026/2027", "semester": "harmattan"})
        cgpa = self.client.get(reverse("student-cgpa", kwargs={"student_id": self.student.pk}))
        self.assertEqual(gpa.status_code, 200)
        self.assertEqual(Decimal(gpa.data["gpa"]), Decimal("2"))
        self.assertEqual(cgpa.status_code, 200)
        self.assertEqual(Decimal(cgpa.data["cgpa"]), Decimal("2"))
        self.assertEqual(cgpa.data["history_completeness"], "not_confirmed")

    def test_gpa_requires_existing_session_and_semester(self):
        self.client.force_authenticate(self.hod)
        url = reverse("student-gpa", kwargs={"student_id": self.student.pk})
        for params in ({}, {"academic_session": "2030/2031", "semester": "rain"},
                       {"academic_session": "2026/2027", "semester": "bad"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(url, params).status_code, 400)

    def test_empty_history_returns_null(self):
        self.client.force_authenticate(self.hod)
        response = self.client.get(reverse("student-cgpa", kwargs={"student_id": self.student.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["cgpa"])

    def test_unverified_failure_blocks_cgpa(self):
        self.make_verified_result()
        Result.objects.create(student=self.student, offering=self.offering,
                              attempt_number=2, score=Decimal("30"), credit_units=3)
        self.client.force_authenticate(self.hod)
        response = self.client.get(reverse("student-cgpa", kwargs={"student_id": self.student.pk}))
        self.assertEqual(response.status_code, 400)

    def test_student_reads_own_verified_results_only(self):
        verified = self.make_verified_result()
        pending = Result.objects.create(student=self.student, offering=self.offering,
                                        attempt_number=2, score=Decimal("75"), credit_units=3)
        other = Student.objects.create(identifier_type="matriculation", identifier_value="009999",
            full_name="Other Student", phone_number="08000000001", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        foreign = Result.objects.create(student=other, offering=self.offering,
            score=Decimal("75"), credit_units=3, is_verified=True)
        self.student_login()
        response = self.client.get(reverse("my-results"), {"student_id": str(other.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [verified.pk])
        for record in (pending, foreign):
            self.assertEqual(self.client.get(reverse("my-result-detail",
                kwargs={"result_id": record.pk})).status_code, 404)
        self.assertEqual(self.client.get(reverse("my-result-detail",
            kwargs={"result_id": verified.pk})).status_code, 200)

    def test_student_cannot_use_hod_or_write_endpoints(self):
        result = self.make_verified_result()
        self.student_login()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)
        self.assertEqual(self.client.patch(reverse("result-score-update",
            kwargs={"result_id": result.pk}), {"score": "75"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(reverse("result-verify",
            kwargs={"result_id": result.pk}), {"expected_score": "68"}, format="json").status_code, 403)
        self.assertEqual(self.client.get(reverse("student-cgpa",
            kwargs={"student_id": self.student.pk})).status_code, 403)

    def test_student_own_gpa_and_cgpa(self):
        self.make_verified_result()
        self.student_login()
        cgpa = self.client.get(reverse("my-cgpa"))
        gpa = self.client.get(reverse("my-gpa"),
            {"academic_session": "2026/2027", "semester": "harmattan"})
        self.assertEqual(cgpa.status_code, 200)
        self.assertEqual(gpa.status_code, 200)
        self.assertEqual(Decimal(cgpa.data["cgpa"]), Decimal("4"))
        self.assertEqual(Decimal(gpa.data["gpa"]), Decimal("4"))

    def test_unlinked_account_cannot_use_student_endpoints(self):
        user = get_user_model().objects.create_user(username="unlinked")
        self.client.force_authenticate(user)
        for name in ("my-results", "my-cgpa", "my-gpa"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 404)

    def test_anonymous_access_is_denied(self):
        for name in ("my-results", "my-cgpa", "course-list", "result-create"):
            self.assertIn(self.client.get(reverse(name)).status_code, (401, 403))

    def test_hod_can_create_catalog_and_reject_invalid_session(self):
        self.client.force_authenticate(self.hod)
        url = reverse("academic-session-list")
        self.assertEqual(self.client.post(url, {"name": "2027/2029"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"name": "2027/2028"}, format="json").status_code, 201)
        course = self.client.post(reverse("course-list"),
            {"code": "EEE302", "title": "Example second course"}, format="json")
        self.assertEqual(course.status_code, 201)
        payload = {"course": course.data["id"], "academic_session": self.offering.academic_session_id,
                   "semester": "rain", "level": 300, "credit_units": 2}
        self.assertEqual(self.client.post(reverse("course-offering-list"), payload, format="json").status_code, 201)
        self.assertEqual(self.client.post(reverse("course-offering-list"), payload, format="json").status_code, 400)

    def test_staff_cannot_manage_catalog(self):
        self.client.force_authenticate(self.staff)
        for name in ("academic-session-list", "course-list", "course-offering-list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
            self.assertEqual(self.client.post(reverse(name), {}, format="json").status_code, 403)

    def test_session_writes_require_csrf(self):
        from rest_framework.test import APIClient
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.hod)
        self.assertEqual(client.post(self.url, self.payload, format="json").status_code, 403)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        response = client.post(self.url, self.payload, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)
