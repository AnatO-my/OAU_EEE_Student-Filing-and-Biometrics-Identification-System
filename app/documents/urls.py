from django.urls import path

from .views import StudentDocumentView

urlpatterns = [
    path(
        "students/<uuid:student_id>/documents/",
        StudentDocumentView.as_view(),
        name="student-documents",
    ),
]
from .views import DocumentDownloadView, DocumentReviewView
urlpatterns += [path("documents/<uuid:document_id>/download/",DocumentDownloadView.as_view(),name="document-download"),path("documents/<uuid:document_id>/review/",DocumentReviewView.as_view(),name="document-review")]
