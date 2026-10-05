from rest_framework import generics, permissions, filters
from rest_framework.pagination import PageNumberPagination
from django.conf import settings

from .models import Student
from .serializers import StudentSerializer, StudentFilterSerializer
from .permissions import StudentModelPermissions
from .services import students_visible_to


# class built for controlling the number of students to be displayed per page
class StudentPagination(PageNumberPagination):
    page_size = 20


# class built for listing students with filtering and searching capabilities
class StudentListView(generics.ListAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser, StudentModelPermissions]
    filter_backends = [filters.SearchFilter]
    search_fields = ["full_name", "identifier_value"]
    pagination_class = StudentPagination

    # method to get the queryset of students based on the provided filters
    def get_queryset(self):
        query_filters = StudentFilterSerializer(data=self.request.query_params.dict())
        query_filters.is_valid(raise_exception=True)

        return students_visible_to(
            self.request.user,
            settings.CURRENT_ACADEMIC_SESSION,
        ).filter(**query_filters.validated_data)


class StudentDetailView(generics.RetrieveAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser, StudentModelPermissions]
    lookup_field = "student_id"

    def get_queryset(self):
        return students_visible_to(
            self.request.user,
            settings.CURRENT_ACADEMIC_SESSION,
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
