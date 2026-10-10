from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from students.models import Student

from .grading import grade_point_for_score
from .models import CourseOffering, GradingScale, Result
from .access import require_result_access


@transaction.atomic
def create_result(
    *,
    user,
    student,
    offering,
    score=None,
    attempt_number=1,
):
    student = Student.objects.select_for_update().get(pk=student.pk)
    require_result_access(user, student, "add_result")
    if student.academic_status == Student.AcademicStatus.GRADUATED:
        raise ValidationError("Reopen academic status before changing a graduated student's results.")
    offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)

    scale = GradingScale.objects.select_for_update().get(pk=offering.grading_scale_id)
    if not scale.is_published:
        raise ValidationError("Select a published grading version for this offering.")
    if score is not None:
        grade_point_for_score(score, grading_scale=scale)

    result = Result(
        student=student,
        offering=offering,
        attempt_number=attempt_number,
        score=score,
        credit_units=offering.credit_units,
        grading_scale=scale,
        is_verified=False,
    )

    result.full_clean()
    result.save()

    return result


@transaction.atomic
def update_result_score(*, user, result, score):
    student = Student.objects.select_for_update().get(pk=result.student_id)
    require_result_access(user, student, "change_result")
    if student.academic_status == Student.AcademicStatus.GRADUATED:
        raise ValidationError("Reopen academic status before changing a graduated student's results.")
    result = Result.objects.select_for_update().get(pk=result.pk)

    if score is not None:
        grade_point_for_score(score, grading_scale=result.grading_scale)

    if result.score == score:
        return result

    result.score = score
    result.is_verified = False

    result.full_clean()
    result.save(update_fields=["score", "is_verified"])

    return result


@transaction.atomic
def verify_result(*, user, result, expected_score):
    student = Student.objects.select_for_update().get(pk=result.student_id)
    require_result_access(user, student, "verify_result")
    if student.academic_status == Student.AcademicStatus.GRADUATED:
        raise ValidationError("Reopen academic status before changing a graduated student's results.")
    result = Result.objects.select_for_update().get(pk=result.pk)

    # Both values must be valid scores; missing scores cannot be verified.
    grade_point_for_score(expected_score, grading_scale=result.grading_scale)
    grade_point_for_score(result.score, grading_scale=result.grading_scale)

    if result.score != expected_score:
        raise ValidationError(
            {"score": "The score has changed. Refresh and review it again."}
        )

    result.full_clean()
    result.is_verified = True
    result.save(update_fields=["is_verified"])

    return result


def require_hod(user):
    if not (user.is_authenticated and user.is_active and user.is_staff and user.is_superuser):
        raise PermissionDenied("Only the active HOD may manage grading versions.")


@transaction.atomic
def create_grading_scale(*, user, validated_data):
    require_hod(user)
    scale = GradingScale(**validated_data, is_published=False)
    scale.save()
    return scale


@transaction.atomic
def update_grading_scale(*, user, scale, validated_data):
    require_hod(user)
    scale = GradingScale.objects.select_for_update().get(pk=scale.pk)
    if scale.is_published:
        raise ValidationError("Published grading versions are locked. Create a new version.")
    for field in ("name", "bands"):
        if field in validated_data:
            setattr(scale, field, validated_data[field])
    scale.save()
    return scale


@transaction.atomic
def publish_grading_scale(*, user, scale):
    require_hod(user)
    scale = GradingScale.objects.select_for_update().get(pk=scale.pk)
    scale.is_published = True
    scale.save()
    return scale


@transaction.atomic
def assign_offering_scale(*, user, offering, scale):
    require_hod(user)
    offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)
    scale = GradingScale.objects.select_for_update().get(pk=scale.pk)
    if not scale.is_published:
        raise ValidationError("Select a published grading version.")
    if offering.results.exists():
        raise ValidationError("An offering with results cannot change its grading version.")
    offering.grading_scale = scale
    offering.full_clean()
    offering.save(update_fields=["grading_scale"])
    return offering
