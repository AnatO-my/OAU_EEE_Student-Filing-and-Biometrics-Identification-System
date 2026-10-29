from django.urls import path
from .batch_views import StudentWorkflowView, StudentRequestReviewView, HandoverView, PerformanceReviewView
urlpatterns = [path('workflows/students/<uuid:student_id>/', StudentWorkflowView.as_view(), name='student-workflow'), path('workflows/requests/<int:request_id>/review/', StudentRequestReviewView.as_view(), name='student-request-review'), path('workflows/handover/', HandoverView.as_view(), name='hod-handover'), path('workflows/source-comparisons/<int:source_id>/review/', PerformanceReviewView.as_view(), name='source-comparison-review')]
