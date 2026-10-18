from academics.session_context import current_session_name
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions

from academics.views import run_academic_service
from .models import Guardian
from .serializers import ScopedGuardianSerializer
from .services import create_guardian, update_guardian, students_visible_to
from .views import StudentPagination


# Enforce staff status, student/guardian visibility, and action-specific rights.
class GuardianAccess(permissions.BasePermission):
    # Check shared guardian access requirements for the requested HTTP action.
    def has_permission(self, request, view):
        user = request.user
        action = {"POST": "add_guardian", "PATCH": "change_guardian"}.get(request.method, "view_guardian")
        return (user.is_authenticated and user.is_active and user.is_staff
                and user.has_perm("students.view_student")
                and user.has_perm("students.view_guardian")
                and user.has_perm("students." + action))


# List guardians for an in-scope student and create records through the service.
class GuardianListCreateView(generics.ListCreateAPIView):
    permission_classes = [GuardianAccess]
    serializer_class = ScopedGuardianSerializer
    pagination_class = StudentPagination

    # Resolve the requested student only within the caller's visible students.
    def parent(self):
        return get_object_or_404(students_visible_to(self.request.user,
            current_session_name()), pk=self.kwargs["student_id"])

    # Return guardians in a stable identifier order for the scoped parent.
    def get_queryset(self):
        return self.parent().guardians.order_by("guardian_id")

    # Check parent visibility before accepting any submitted guardian data.
    def create(self, request, *args, **kwargs):
        self.parent()  # Check parent scope before processing write data.
        return super().create(request, *args, **kwargs)

    # Delegate validated creation to the transactional guardian service.
    def perform_create(self, serializer):
        serializer.instance = run_academic_service(create_guardian,
            user=self.request.user, student=self.parent(), validated_data=serializer.validated_data)


# Retrieve or edit one guardian only through its visible parent student.
class GuardianDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [GuardianAccess]
    serializer_class = ScopedGuardianSerializer
    lookup_url_kwarg = "guardian_id"
    http_method_names = ["get", "patch", "head", "options"]

    # Restrict lookup to guardians attached to this visible student.
    def get_queryset(self):
        students = students_visible_to(self.request.user, current_session_name())
        return Guardian.objects.filter(student__in=students, student_id=self.kwargs["student_id"])

    # Delegate validated edits to the transactional guardian service.
    def perform_update(self, serializer):
        serializer.instance = run_academic_service(update_guardian,
            user=self.request.user, guardian=serializer.instance, validated_data=serializer.validated_data)
