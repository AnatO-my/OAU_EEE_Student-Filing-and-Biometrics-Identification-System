from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import AdviserAssignment

from .eligibility import validate_graduation_cgpa
from .models import Guardian, Student


def students_visible_to(user, academic_session):
    students = Student.objects.all()

    if not user.is_authenticated or not user.is_active:
        return students.none()

    if user.is_superuser:
        return students

    if not user.is_staff or not user.has_perm("students.view_student"):
        return students.none()

    if not academic_session:
        return students.none()

    assigned_levels = user.adviser_assignments.filter(
        academic_session=academic_session,
        is_active=True,
    ).values_list("level", flat=True)

    return students.filter(current_level__in=assigned_levels)


@transaction.atomic
def create_student(*, user, validated_data):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        raise PermissionDenied("An active staff account is required.")

    if not user.has_perm("students.add_student"):
        raise PermissionDenied("You do not have permission to create students.")

    target_status = validated_data.get(
        "academic_status",
        Student.AcademicStatus.UNDERGRADUATE,
    )

    if not user.is_superuser:
        academic_session = settings.CURRENT_ACADEMIC_SESSION

        if not academic_session:
            raise PermissionDenied("The current academic session is not configured.")

        assignment = (
            AdviserAssignment.objects.select_for_update()
            .filter(
                staff=user,
                academic_session=academic_session,
                level=validated_data["current_level"],
                is_active=True,
            )
            .first()
        )

        if assignment is None:
            raise PermissionDenied("You cannot create students in this level.")

        if target_status != Student.AcademicStatus.UNDERGRADUATE:
            raise PermissionDenied("Only the HOD may register a student as graduated.")

    if target_status == Student.AcademicStatus.GRADUATED:
        # A newly created student has no reviewed academic history.
        validate_graduation_cgpa(None)

    return Student.objects.create(**validated_data)


@transaction.atomic
def update_student(*, user, student, validated_data):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        raise PermissionDenied("An active staff account is required.")

    if not user.has_perm("students.change_student"):
        raise PermissionDenied("You do not have permission to edit students.")

    student = Student.objects.select_for_update().get(pk=student.pk)

    target_status = validated_data.get(
        "academic_status",
        student.academic_status,
    )
    target_level = validated_data.get(
        "current_level",
        student.current_level,
    )
    if student.academic_status == Student.AcademicStatus.GRADUATED and target_status == Student.AcademicStatus.GRADUATED:
        if any(validated_data.get(field, getattr(student, field)) != getattr(student, field)
               for field in ("current_level", "admission_year", "mode_of_admission")):
            raise ValidationError("Reopen academic status before changing a graduated student's academic profile.")


    if not user.is_superuser:
        if target_status != student.academic_status:
            raise PermissionDenied("Only the HOD may change academic status.")

        if target_level != student.current_level:
            raise PermissionDenied("Only the HOD may change a student's level.")

        academic_session = settings.CURRENT_ACADEMIC_SESSION

        if not academic_session:
            raise PermissionDenied("The current academic session is not configured.")

        assignment = (
            AdviserAssignment.objects.select_for_update()
            .filter(
                staff=user,
                academic_session=academic_session,
                is_active=True,
                level=student.current_level,
            )
            .first()
        )

        if assignment is None:
            raise PermissionDenied(
                "You cannot edit students outside your assigned level."
            )

    if (
        target_status == Student.AcademicStatus.GRADUATED
        and student.academic_status != Student.AcademicStatus.GRADUATED
    ):
        from academics.graduation import require_graduation_ready
        from django.core.exceptions import ValidationError as ModelValidationError
        if any(validated_data.get(field, getattr(student, field)) != getattr(student, field)
               for field in ("current_level", "admission_year", "mode_of_admission")):
            raise ValidationError({"academic_status": "Save academic profile changes and obtain a new HOD review first."})
        try:
            require_graduation_ready(student)
        except ModelValidationError as exc:
            raise ValidationError({"academic_status": exc.messages}) from exc

    for field, value in validated_data.items():
        setattr(student, field, value)

    student.save()
    return student


@transaction.atomic
def bulk_change_student_levels(*, user, validated_data):
    if (
        not user.is_authenticated
        or not user.is_active
        or not user.is_staff
        or not user.is_superuser
    ):
        raise PermissionDenied(
            "Only the active HOD superuser may change student levels."
        )

    student_ids = validated_data["student_ids"]
    expected_level = validated_data["expected_level"]
    target_level = validated_data["current_level"]

    if target_level == expected_level:
        raise ValidationError(
            {"current_level": "Choose a different destination level."}
        )

    students = list(
        Student.objects.select_for_update().filter(pk__in=student_ids).order_by("pk")
    )

    if len(students) != len(student_ids):
        raise ValidationError(
            {"student_ids": ("The selection contains missing or duplicate students.")}
        )

    if any(student.current_level != expected_level for student in students):
        raise ValidationError(
            {
                "expected_level": (
                    "One or more students have a different current level. "
                    "Refresh the selection."
                )
            }
        )

    if any(student.academic_status == Student.AcademicStatus.GRADUATED for student in students):
        raise ValidationError("Reopen academic status before changing graduated students' levels.")

    for student in students:
        student.current_level = target_level

    Student.objects.bulk_update(students, ["current_level"])
    return len(students)


@transaction.atomic
def bulk_change_student_statuses(*, user, validated_data):
    if (
        not user.is_authenticated
        or not user.is_active
        or not user.is_staff
        or not user.is_superuser
    ):
        raise PermissionDenied(
            "Only the active HOD superuser may change academic status."
        )

    student_ids = validated_data["student_ids"]
    expected_status = validated_data["expected_status"]
    target_status = validated_data["academic_status"]

    if (
        expected_status not in Student.AcademicStatus.values
        or target_status not in Student.AcademicStatus.values
    ):
        raise ValidationError({"academic_status": "Invalid academic status."})

    if target_status == expected_status:
        raise ValidationError(
            {"academic_status": "Choose a different destination status."}
        )

    students = list(
        Student.objects.select_for_update().filter(pk__in=student_ids).order_by("pk")
    )

    if len(students) != len(student_ids):
        raise ValidationError(
            {"student_ids": ("The selection contains missing or duplicate students.")}
        )

    if any(student.academic_status != expected_status for student in students):
        raise ValidationError(
            {
                "expected_status": (
                    "One or more students have a different status. "
                    "Refresh the selection."
                )
            }
        )

    if target_status == Student.AcademicStatus.GRADUATED:
        from academics.graduation import require_graduation_ready
        from django.core.exceptions import ValidationError as ModelValidationError
        for student in students:
            try:
                require_graduation_ready(student)
            except ModelValidationError as exc:
                raise ValidationError({"academic_status": exc.messages}) from exc

    for student in students:
        student.academic_status = target_status

    Student.objects.bulk_update(students, ["academic_status"])
    return len(students)


def require_guardian_access(user, student, action):
    if not (user.is_authenticated and user.is_active and user.is_staff
            and user.has_perm("students.view_student")
            and user.has_perm("students.view_guardian")
            and user.has_perm("students." + action)):
        raise PermissionDenied("You do not have permission for this guardian action.")
    if not user.is_superuser:
        if not settings.CURRENT_ACADEMIC_SESSION or not AdviserAssignment.objects.select_for_update().filter(
            staff=user, academic_session=settings.CURRENT_ACADEMIC_SESSION,
            level=student.current_level, is_active=True,
        ).exists():
            raise PermissionDenied("The student is outside your adviser assignment.")


@transaction.atomic
def create_guardian(*, user, student, validated_data):
    student = Student.objects.select_for_update().get(pk=student.pk)
    require_guardian_access(user, student, "add_guardian")
    guardian = Guardian(student=student, **{key: value for key, value in validated_data.items()
        if key in ("full_name", "phone_number", "relationship", "email", "address")})
    guardian.full_clean()
    guardian.save()
    return guardian


@transaction.atomic
def update_guardian(*, user, guardian, validated_data):
    student = Student.objects.select_for_update().get(pk=guardian.student_id)
    require_guardian_access(user, student, "change_guardian")
    guardian = Guardian.objects.select_for_update().get(pk=guardian.pk)
    for key in ("full_name", "phone_number", "relationship", "email", "address"):
        if key in validated_data:
            setattr(guardian, key, validated_data[key])
    guardian.full_clean()
    guardian.save()
    return guardian
