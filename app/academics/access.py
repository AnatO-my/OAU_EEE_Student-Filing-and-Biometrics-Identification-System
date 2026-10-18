from academics.session_context import current_session_name
from django.conf import settings
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from accounts.models import AdviserAssignment
from students.models import Student
from students.services import students_visible_to


# Require an active staff account with both student-read and action-specific result permissions.
def has_result_permission(user, action="view_result"):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return (user.has_perm("students.view_student")
            and user.has_perm("academics.view_result")
            and user.has_perm("academics." + action))


# Limit student users to their linked record and staff to students visible in the current session.
def academic_students_for(user):
    if user.is_authenticated and user.is_active and not user.is_staff:
        return Student.objects.filter(user=user)
    if not has_result_permission(user):
        return Student.objects.none()
    return students_visible_to(user, current_session_name())


# Enforce the requested result permission and the staff member's current adviser assignment.
def require_result_access(user, student, action):
    if not has_result_permission(user, action):
        raise PermissionDenied("You do not have permission for this result action.")
    if user.is_superuser:
        return
    session = current_session_name()
    if not session or not AdviserAssignment.objects.select_for_update().filter(
        staff=user, academic_session=session, level=student.current_level,
        is_active=True,
    ).exists():
        raise PermissionDenied("This student is outside your current adviser assignment.")


# Resolve endpoint-specific result actions before checking the request user's permissions.
class ResultAccessPermission(BasePermission):
    # Map HTTP methods to default result permissions unless the view names its own action.
    def has_permission(self, request, view):
        action = getattr(view, "result_action", None)
        if action is None:
            action = {"POST": "add_result", "PATCH": "change_result"}.get(
                request.method, "view_result"
            )
        return has_result_permission(request.user, action)
