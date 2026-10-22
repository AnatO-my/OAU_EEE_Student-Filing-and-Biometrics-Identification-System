from academics.session_context import current_session_name
from rest_framework import generics, permissions, filters
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as ModelValidationError

from .models import Student
from .serializers import StudentSerializer, StudentFilterSerializer, BulkStudentStatusSerializer
from .permissions import StudentModelPermissions
from .services import students_visible_to, create_student, update_student, bulk_change_student_statuses


# class built for controlling the number of students to be displayed per page
class StudentPagination(PageNumberPagination):
    page_size = 20


# class built for listing students with filtering and searching capabilities
class StudentListView(generics.ListCreateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser, StudentModelPermissions]
    filter_backends = [filters.SearchFilter]
    search_fields = ["full_name", "identifier_value"]
    pagination_class = StudentPagination

    # Create a record through the service that enforces staff and assignment rules.
    def perform_create(self, serializer):
        serializer.instance = create_student(
            user=self.request.user,
            validated_data=serializer.validated_data,
        )

    # method to get the queryset of students based on the provided filters
    def get_queryset(self):
        query_filters = StudentFilterSerializer(data=self.request.query_params.dict())
        query_filters.is_valid(raise_exception=True)

        return students_visible_to(
            self.request.user,
            current_session_name(),
        ).filter(**query_filters.validated_data)


# Retrieve or edit one student within the caller's current-session visibility.
class StudentDetailView(generics.RetrieveUpdateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser, StudentModelPermissions]
    lookup_field = "student_id"
    http_method_names = ["get", "patch", "head", "options"]

    # Limit detail lookup to students visible under the current assignment.
    def get_queryset(self):
        return students_visible_to(
            self.request.user,
            current_session_name(),
        )

    # Delegate edits to the transactional service that enforces change rules.
    def perform_update(self, serializer):
        serializer.instance = update_student(
            user=self.request.user,
            student=serializer.instance,
            validated_data=serializer.validated_data,
        )


# Give an authenticated student access to only their linked profile.
class MyStudentProfileView(generics.RetrieveAPIView):
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Resolve the profile directly from the authenticated account.
    def get_object(self):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(
            Student,
            user=self.request.user,
        )


from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.views import IsHOD
from .serializers import BulkStudentLevelSerializer
from .services import bulk_change_student_levels
from .identity import resolve_student_identifier
from .serializers import StudentLookupSerializer, StudentIdentifierPromotionSerializer
from .services import promote_student_identifier


class StudentIdentifierLookupView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        if not request.user.has_perm("students.view_student"):
            self.permission_denied(request)
        serializer = StudentLookupSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            student = resolve_student_identifier(**serializer.validated_data,
                queryset=students_visible_to(request.user, current_session_name()))
        except ModelValidationError as error:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(error.messages) from None
        if student is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("No matching student is available in your access scope.")
        return Response(StudentSerializer(student).data)


class StudentIdentifierPromotionView(APIView):
    permission_classes = [IsHOD]

    def post(self, request, student_id):
        serializer = StudentIdentifierPromotionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = get_object_or_404(Student, pk=student_id)
        try:
            student = promote_student_identifier(user=request.user, student=student,
                **serializer.validated_data)
        except ModelValidationError as error:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(error.messages) from None
        return Response(StudentSerializer(student).data)


# Accept atomic level-change requests from the HOD only.
class BulkStudentLevelView(APIView):
    # Validate the selection and report how many records were changed.
    permission_classes = [IsHOD]

    def post(self, request):
        serializer = BulkStudentLevelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = bulk_change_student_levels(
            user=request.user, validated_data=serializer.validated_data,
        )
        return Response({"updated_count": count,
                         "current_level": serializer.validated_data["current_level"]})

# Accept atomic academic-status changes from the HOD only.
class BulkStudentStatusView(APIView):
    # Validate status changes and report the resulting status and count.
    permission_classes = [IsHOD]

    def post(self, request):
        serializer = BulkStudentStatusSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        count = bulk_change_student_statuses(
            user=request.user,
            validated_data=serializer.validated_data,
        )

        return Response({
            "updated_count": count,
            "academic_status": (
                serializer.validated_data["academic_status"]
            ),
        })
