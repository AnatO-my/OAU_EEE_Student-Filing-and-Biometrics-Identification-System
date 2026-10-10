from decimal import Decimal

from django.core.exceptions import ValidationError

from .grading import grade_point_for_score


def calculate_weighted_average(results):
    total_quality_points = Decimal("0")
    total_units = 0

    for result in results:
        if not result.is_verified:
            raise ValidationError("Verify every supplied result before calculating.")

        units = result.credit_units
        if isinstance(units, bool) or not isinstance(units, int) or units <= 0:
            raise ValidationError(
                "Every result must have positive integer credit units."
            )

        grade_point = grade_point_for_score(
            result.score, grading_scale=getattr(result, "grading_scale", None)
        )
        total_quality_points += grade_point * units
        total_units += units

    if total_units == 0:
        return None

    return total_quality_points / Decimal(total_units)


def calculate_student_cgpa(*, student):
    results = student.results.select_related("grading_scale").order_by("pk")

    return calculate_weighted_average(results)


def calculate_student_gpa(
    *,
    student,
    academic_session,
    semester,
):
    from .models import CourseOffering

    if semester not in CourseOffering.Semester.values:
        raise ValidationError(
            {"semester": "Select a valid semester."}
        )

    results = student.results.filter(
        offering__academic_session=academic_session,
        offering__semester=semester,
    ).select_related("grading_scale").order_by("pk")

    return calculate_weighted_average(results)