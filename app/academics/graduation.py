import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from students.models import Student
from students.eligibility import validate_graduation_cgpa
from .calculations import calculate_weighted_average
from .models import CourseRequirement, GraduationReview
from .services import require_hod


def reviewed_history(student):
    results = list(student.results.select_related("grading_scale").order_by("pk"))
    requirements = list(student.course_requirements.order_by("pk"))
    if not requirements:
        raise ValidationError("Record the reviewed course requirements before approving graduation.")
    cgpa = calculate_weighted_average(results)
    validate_graduation_cgpa(cgpa)
    recorded = {result.offering_id for result in results}
    for requirement in requirements:
        requirement.full_clean()
        if requirement.resolution == CourseRequirement.Resolution.RESULT and requirement.offering_id not in recorded:
            raise ValidationError("A required course offering has no recorded result.")
    snapshot = {
        "student": str(student.pk), "level": student.current_level,
        "admission_year": student.admission_year, "mode_of_admission": student.mode_of_admission,
        "results": [{"id": result.pk, "offering": result.offering_id,
            "attempt": result.attempt_number, "score": str(result.score),
            "units": result.credit_units, "verified": result.is_verified,
            "scale": result.grading_scale_id} for result in results],
        "requirements": [{"id": row.pk, "offering": row.offering_id,
            "resolution": row.resolution, "reason": row.reason} for row in requirements],
    }
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return cgpa, digest


@transaction.atomic
def approve_graduation(*, user, student, notes, expected_digest):
    require_hod(user)
    student = Student.objects.select_for_update().get(pk=student.pk)
    if not notes.strip():
        raise ValidationError({"notes": "Record the basis of the HOD review."})
    cgpa, digest = reviewed_history(student)
    if expected_digest != digest:
        raise ValidationError("Academic history changed. Refresh the review preview.")
    review, _ = GraduationReview.objects.update_or_create(student=student, defaults={
        "reviewed_by": user, "reviewed_at": timezone.now(), "notes": notes,
        "history_digest": digest, "cgpa_snapshot": str(cgpa),
    })
    return review


def require_graduation_ready(student):
    cgpa, digest = reviewed_history(student)
    review = GraduationReview.objects.filter(student=student).first()
    if review is None or review.history_digest != digest:
        raise ValidationError("The HOD must approve the current academic history before graduation.")
    return cgpa


@transaction.atomic
def save_course_requirement(*, user, student, validated_data, requirement=None):
    require_hod(user)
    student = Student.objects.select_for_update().get(pk=student.pk)
    if student.academic_status == Student.AcademicStatus.GRADUATED:
        raise ValidationError("Reopen academic status before changing a graduated student's requirements.")
    if requirement is None:
        requirement = CourseRequirement(student=student, recorded_by=user)
    else:
        requirement = CourseRequirement.objects.select_for_update().get(pk=requirement.pk, student=student)
    for field in ("offering", "resolution", "reason"):
        if field in validated_data:
            setattr(requirement, field, validated_data[field])
    requirement.recorded_by = user
    requirement.full_clean()
    requirement.save()
    return requirement
