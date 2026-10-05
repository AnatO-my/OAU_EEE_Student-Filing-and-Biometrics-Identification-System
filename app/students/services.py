from .models import Student


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