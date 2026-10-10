from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions

from academics.views import run_academic_service
from .models import Guardian
from .serializers import ScopedGuardianSerializer
from .services import create_guardian, update_guardian, students_visible_to
from .views import StudentPagination


class GuardianAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        action = {"POST": "add_guardian", "PATCH": "change_guardian"}.get(request.method, "view_guardian")
        return (user.is_authenticated and user.is_active and user.is_staff
                and user.has_perm("students.view_student")
                and user.has_perm("students.view_guardian")
                and user.has_perm("students." + action))


class GuardianListCreateView(generics.ListCreateAPIView):
    permission_classes = [GuardianAccess]
    serializer_class = ScopedGuardianSerializer
    pagination_class = StudentPagination

    def parent(self):
        return get_object_or_404(students_visible_to(self.request.user,
            settings.CURRENT_ACADEMIC_SESSION), pk=self.kwargs["student_id"])

    def get_queryset(self):
        return self.parent().guardians.order_by("guardian_id")

    def create(self, request, *args, **kwargs):
        self.parent()  # Check parent scope before processing write data.
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.instance = run_academic_service(create_guardian,
            user=self.request.user, student=self.parent(), validated_data=serializer.validated_data)


class GuardianDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [GuardianAccess]
    serializer_class = ScopedGuardianSerializer
    lookup_url_kwarg = "guardian_id"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        students = students_visible_to(self.request.user, settings.CURRENT_ACADEMIC_SESSION)
        return Guardian.objects.filter(student__in=students, student_id=self.kwargs["student_id"])

    def perform_update(self, serializer):
        serializer.instance = run_academic_service(update_guardian,
            user=self.request.user, guardian=serializer.instance, validated_data=serializer.validated_data)
