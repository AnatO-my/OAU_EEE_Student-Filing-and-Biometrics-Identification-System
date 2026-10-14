from rest_framework import generics, permissions, filters
from rest_framework.pagination import PageNumberPagination
from django.conf import settings

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
            settings.CURRENT_ACADEMIC_SESSION,
        ).filter(**query_filters.validated_data)


class StudentDetailView(generics.RetrieveUpdateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser, StudentModelPermissions]
    lookup_field = "student_id"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return students_visible_to(
            self.request.user,
            settings.CURRENT_ACADEMIC_SESSION,
        )

    def perform_update(self, serializer):
        serializer.instance = update_student(
            user=self.request.user,
            student=serializer.instance,
            validated_data=serializer.validated_data,
        )


class MyStudentProfileView(generics.RetrieveAPIView):
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

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


class BulkStudentLevelView(APIView):
    permission_classes = [IsHOD]

    def post(self, request):
        serializer = BulkStudentLevelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = bulk_change_student_levels(
            user=request.user, validated_data=serializer.validated_data,
        )
        return Response({"updated_count": count,
                         "current_level": serializer.validated_data["current_level"]})

class BulkStudentStatusView(APIView):
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