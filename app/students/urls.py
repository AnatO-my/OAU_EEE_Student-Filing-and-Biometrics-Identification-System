from django.urls import path

from .views import (
    StudentListView,
    StudentDetailView,
    MyStudentProfileView,
    BulkStudentLevelView,
    BulkStudentStatusView,
)

from .export_views import StudentExportView

urlpatterns = [
    path("students/export/", StudentExportView.as_view(), name="student-export"),
    path(
        "students/bulk-level-change/",
        BulkStudentLevelView.as_view(),
        name="bulk-student-level-change",
    ),
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
    path(
        "students/bulk-status-change/",
        BulkStudentStatusView.as_view(),
        name="bulk-student-status-change",
    ),
]

from .guardian_views import GuardianListCreateView, GuardianDetailView

urlpatterns += [
    path("students/<uuid:student_id>/guardians/", GuardianListCreateView.as_view(), name="guardian-list"),
    path("students/<uuid:student_id>/guardians/<uuid:guardian_id>/", GuardianDetailView.as_view(), name="guardian-detail"),
]

from accounts.lifecycle_views import StudentAccountView
urlpatterns += [path("students/<uuid:student_id>/account/", StudentAccountView.as_view(), name="student-account")]
