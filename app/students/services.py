from academics.session_context import current_session_name
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from accounts.models import AdviserAssignment

from .eligibility import validate_graduation_cgpa
from .models import Guardian, Student, StudentIdentityChange
from .identity import identifier_key, identifier_is_unavailable


def reject_unavailable_identifier(value, student_id=None):
    if identifier_is_unavailable(value, student_id):
        raise ValidationError({"identifier_value": "This identifier is unavailable. Check the entry or ask the HOD to review it."})


def save_registered_student(student):
    try:
        with transaction.atomic():
            student.save()
    except IntegrityError:
        # The shared registry and primary key uniqueness enforce the same rule
        # when another registration/promotion wins after the preliminary lookup.
        reject_unavailable_identifier(student.identifier_value, student.pk)
        raise
    return student


# Return only active-session students visible under the user's staff role.
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


# Create a student after checking staff rights, adviser scope, and graduation eligibility.
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
        academic_session = current_session_name()

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

    reject_unavailable_identifier(validated_data["identifier_value"])
    return save_registered_student(Student(**validated_data))


# Update a locked student record while enforcing adviser and HOD boundaries.
@transaction.atomic
def update_student(*, user, student, validated_data):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        raise PermissionDenied("An active staff account is required.")

    if not user.has_perm("students.change_student"):
        raise PermissionDenied("You do not have permission to edit students.")

    student = Student.objects.select_for_update().get(pk=student.pk)

    if (("identifier_type" in validated_data and validated_data["identifier_type"] != student.identifier_type)
            or ("identifier_value" in validated_data and identifier_key(validated_data["identifier_value"]) != student.identifier_key)):
        raise ValidationError({"identifier_value": "Use the HOD identifier-promotion action to change a student's identity."})

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

        academic_session = current_session_name()

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

    return save_registered_student(student)


@transaction.atomic
def promote_student_identifier(*, user, student, identifier_value,
                               expected_identifier_type, expected_identifier_value):
    if not (user.is_authenticated and user.is_active and user.is_staff and user.is_superuser):
        raise PermissionDenied("Only the active HOD may promote student identifiers.")
    student = Student.objects.select_for_update().get(pk=student.pk)
    if (student.identifier_type != expected_identifier_type or
            student.identifier_key != identifier_key(expected_identifier_value)):
        raise ValidationError("The student identity changed. Refresh the record before continuing.")
    if student.identifier_type != Student.IdentifierType.UTME:
        raise ValidationError("Only a UTME identifier can be promoted to a matriculation number.")
    reject_unavailable_identifier(identifier_value, student.pk)
    previous_type, previous_value = student.identifier_type, student.identifier_value
    student.identifier_type = Student.IdentifierType.MATRICULATION
    student.identifier_value = identifier_value.strip()
    save_registered_student(student)
    StudentIdentityChange.objects.create(student=student, previous_type=previous_type,
        previous_value=previous_value, identifier_type=student.identifier_type,
        identifier_value=student.identifier_value, actor=user)
    return student


# Apply a level change atomically after validating HOD authority and every selection.
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


# Apply an academic-status change atomically after validating eligibility.
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


# Require guardian permissions and, for advisers, a current matching assignment.
def require_guardian_access(user, student, action):
    if not (user.is_authenticated and user.is_active and user.is_staff
            and user.has_perm("students.view_student")
            and user.has_perm("students.view_guardian")
            and user.has_perm("students." + action)):
        raise PermissionDenied("You do not have permission for this guardian action.")
    if not user.is_superuser:
        if not current_session_name() or not AdviserAssignment.objects.select_for_update().filter(
            staff=user, academic_session=current_session_name(),
            level=student.current_level, is_active=True,
        ).exists():
            raise PermissionDenied("The student is outside your adviser assignment.")


# Create a validated guardian while locking its student against concurrent edits.
@transaction.atomic
def create_guardian(*, user, student, validated_data):
    student = Student.objects.select_for_update().get(pk=student.pk)
    require_guardian_access(user, student, "add_guardian")
    guardian = Guardian(student=student, **{key: value for key, value in validated_data.items()
        if key in ("full_name", "phone_number", "relationship", "email", "address")})
    guardian.full_clean()
    guardian.save()
    return guardian


# Update allowed guardian contact fields while preserving the student relationship.
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
