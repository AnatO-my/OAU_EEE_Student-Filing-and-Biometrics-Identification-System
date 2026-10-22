from django.urls import path
from . import views
from .pending_views import PendingBatchPreviewView, PendingBatchesView

urlpatterns = [
    path("attendance/offerings/<int:offering_id>/roster/", views.RosterView.as_view()),
    path("attendance/offerings/<int:offering_id>/staff/", views.AssignmentView.as_view()),
    path("attendance/sessions/", views.SessionsView.as_view()),
    path("attendance/sessions/<uuid:session_id>/", views.SessionView.as_view()),
    path("attendance/sessions/<uuid:session_id>/close/", views.CloseView.as_view()),
    path("attendance/sessions/<uuid:session_id>/records/", views.RecordsView.as_view()),
    path("attendance/sessions/<uuid:session_id>/pending-batches/preview/", PendingBatchPreviewView.as_view()),
    path("attendance/sessions/<uuid:session_id>/pending-batches/", PendingBatchesView.as_view()),
    path("attendance/records/<int:record_id>/correct/", views.CorrectionView.as_view()),
    path("me/attendance/", views.MyAttendanceView.as_view()),
]
