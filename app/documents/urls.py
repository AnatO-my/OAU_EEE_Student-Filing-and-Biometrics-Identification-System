from django.urls import path

from .views import StudentDocumentView

urlpatterns = [
    path(
        "students/<uuid:student_id>/documents/",
        StudentDocumentView.as_view(),
        name="student-documents",
    ),
]