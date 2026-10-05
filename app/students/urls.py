from django.urls import path

from .views import StudentListView, StudentDetailView, MyStudentProfileView

urlpatterns = [
    path("students/", StudentListView.as_view(), name="student-list"),
    path(
        "students/<uuid:student_id>/",
        StudentDetailView.as_view(),
        name="student-detail",
    ),
    path(
        "me/student/",
        MyStudentProfileView.as_view(),
        name="my-student-profile",
    ),
]
