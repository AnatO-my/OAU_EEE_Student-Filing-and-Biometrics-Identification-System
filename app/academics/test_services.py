from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from app.academics.calculations import calculate_student_cgpa
from students.models import Student

from .models import AcademicSession, Course, CourseOffering, Result
from .services import create_result, update_result_score, verify_result
from .calculations import (
    calculate_student_cgpa,
    calculate_student_gpa,
)


class ResultCreationTests(TestCase):
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

    def create(self, **overrides):
        arguments = {
            "user": self.hod,
            "student": self.student,
            "offering": self.offering,
            "score": Decimal("68.00"),
        }
        arguments.update(overrides)
        return create_result(**arguments)

    def test_units_are_copied_and_result_starts_unverified(self):
        result = self.create()

        result.refresh_from_db()
        self.assertEqual(result.credit_units, 3)
        self.assertEqual(result.score, Decimal("68.00"))
        self.assertFalse(result.is_verified)

        self.offering.credit_units = 4
        self.offering.save(update_fields=["credit_units"])

        result.refresh_from_db()
        self.assertEqual(result.credit_units, 3)

    def test_ordinary_staff_cannot_create_results_yet(self):
        with self.assertRaises(PermissionDenied):
            self.create(user=self.staff)

        self.assertFalse(Result.objects.exists())

    def test_invalid_score_is_not_saved(self):
        with self.assertRaises(ValidationError):
            self.create(score=Decimal("100.01"))

        self.assertFalse(Result.objects.exists())

    def test_duplicate_attempt_does_not_overwrite_result(self):
        original = self.create()

        with self.assertRaises(ValidationError):
            self.create(score=Decimal("75.00"))

        original.refresh_from_db()
        self.assertEqual(original.score, Decimal("68.00"))
        self.assertEqual(Result.objects.count(), 1)

    def test_missing_score_remains_missing(self):
        result = self.create(score=None)

        result.refresh_from_db()
        self.assertIsNone(result.score)
        self.assertFalse(result.is_verified)

    def test_score_correction_resets_verification_and_preserves_units(self):
        result = self.create()
        result.is_verified = True
        result.save(update_fields=["is_verified"])

        self.offering.credit_units = 4
        self.offering.save(update_fields=["credit_units"])

        update_result_score(
            user=self.hod,
            result=result,
            score=Decimal("75.00"),
        )

        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("75.00"))
        self.assertFalse(result.is_verified)
        self.assertEqual(result.credit_units, 3)

    def test_unchanged_score_preserves_verification(self):
        result = self.create()
        result.is_verified = True
        result.save(update_fields=["is_verified"])

        update_result_score(
            user=self.hod,
            result=result,
            score=Decimal("68.00"),
        )

        result.refresh_from_db()
        self.assertTrue(result.is_verified)

    def test_invalid_correction_preserves_existing_result(self):
        result = self.create()
        result.is_verified = True
        result.save(update_fields=["is_verified"])

        with self.assertRaises(ValidationError):
            update_result_score(
                user=self.hod,
                result=result,
                score=Decimal("-0.01"),
            )

        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("68.00"))
        self.assertTrue(result.is_verified)

    def test_ordinary_staff_cannot_correct_results_yet(self):
        result = self.create()

        with self.assertRaises(PermissionDenied):
            update_result_score(
                user=self.staff,
                result=result,
                score=Decimal("75.00"),
            )

        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("68.00"))

    def test_hod_can_verify_reviewed_score(self):
        result = self.create()

        verify_result(
            user=self.hod,
            result=result,
            expected_score=Decimal("68.00"),
        )

        result.refresh_from_db()
        self.assertTrue(result.is_verified)

    def test_changed_score_requires_another_review(self):
        result = self.create()

        update_result_score(
            user=self.hod,
            result=result,
            score=Decimal("75.00"),
        )

        with self.assertRaises(ValidationError):
            verify_result(
                user=self.hod,
                result=result,
                expected_score=Decimal("68.00"),
            )

        result.refresh_from_db()
        self.assertEqual(result.score, Decimal("75.00"))
        self.assertFalse(result.is_verified)

    def test_missing_score_cannot_be_verified(self):
        result = self.create(score=None)

        with self.assertRaises(ValidationError):
            verify_result(
                user=self.hod,
                result=result,
                expected_score=Decimal("68.00"),
            )

        result.refresh_from_db()
        self.assertFalse(result.is_verified)

    def test_ordinary_staff_cannot_verify_results_yet(self):
        result = self.create()

        with self.assertRaises(PermissionDenied):
            verify_result(
                user=self.staff,
                result=result,
                expected_score=Decimal("68.00"),
            )

        result.refresh_from_db()
        self.assertFalse(result.is_verified)

    def test_zero_score_can_be_verified(self):
        result = self.create(score=Decimal("0.00"))

        verify_result(
            user=self.hod,
            result=result,
            expected_score=Decimal("0.00"),
        )

        result.refresh_from_db()
        self.assertTrue(result.is_verified)

    def test_saved_failed_attempt_and_repeat_both_count_in_cgpa(self):
        failed = self.create(score=Decimal("30.00"))
        repeat = self.create(
            score=Decimal("70.00"),
            attempt_number=2,
        )

        for result in (failed, repeat):
            verify_result(
                user=self.hod,
                result=result,
                expected_score=result.score,
            )

        self.assertEqual(
            calculate_student_cgpa(student=self.student),
            Decimal("2.5"),
        )

    def test_student_without_results_has_no_cgpa(self):
        self.assertIsNone(
            calculate_student_cgpa(student=self.student)
        )

    def test_unverified_attempt_blocks_student_cgpa(self):
        verified = self.create(score=Decimal("70.00"))
        verify_result(
            user=self.hod,
            result=verified,
            expected_score=Decimal("70.00"),
        )

        self.create(
            score=Decimal("30.00"),
            attempt_number=2,
        )

        with self.assertRaises(ValidationError):
            calculate_student_cgpa(student=self.student)
    def test_gpa_excludes_other_sessions_and_semesters(self):
        current = self.create(score=Decimal("70.00"))
        verify_result(
            user=self.hod,
            result=current,
            expected_score=Decimal("70.00"),
        )

        other_session = AcademicSession.objects.create(
            name="2025/2026"
        )

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
            # Unverified results outside the selected semester
            # must not block its GPA.
            self.create(
                offering=offering,
                score=Decimal("30.00"),
            )

        self.assertEqual(
            calculate_student_gpa(
                student=self.student,
                academic_session=self.offering.academic_session,
                semester=CourseOffering.Semester.HARMATTAN,
            ),
            Decimal("5"),
        )

    def test_semester_without_results_has_no_gpa(self):
        self.assertIsNone(
            calculate_student_gpa(
                student=self.student,
                academic_session=self.offering.academic_session,
                semester=CourseOffering.Semester.RAIN,
            )
        )

    def test_invalid_semester_is_rejected(self):
        with self.assertRaises(ValidationError):
            calculate_student_gpa(
                student=self.student,
                academic_session=self.offering.academic_session,
                semester="invalid",
            )
