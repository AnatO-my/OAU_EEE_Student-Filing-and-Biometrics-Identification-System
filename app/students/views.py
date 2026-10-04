from rest_framework import generics, permissions, filters

from .models import Student
from .serializers import StudentSerializer, StudentFilterSerializer

from rest_framework.pagination import PageNumberPagination

#class built for controlling the number of students to be displayed per page
class StudentPagination(PageNumberPagination):
    page_size = 20

#class built for listing students with filtering and searching capabilities
class StudentListView(generics.ListAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ["full_name", "identifier_value"]
    pagination_class = StudentPagination

    #method to get the queryset of students based on the provided filters
    def get_queryset(self):
        query_filters = StudentFilterSerializer(
            data=self.request.query_params.dict()
        )
        query_filters.is_valid(raise_exception=True)

        return super().get_queryset().filter(
            **query_filters.validated_data
        )


class StudentDetailView(generics.RetrieveAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = "student_id"
