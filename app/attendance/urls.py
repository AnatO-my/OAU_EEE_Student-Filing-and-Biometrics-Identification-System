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
from .reconciliation_views import (CaptureQueueView, CaptureReviewView, CaptureResolutionView,
                                   ScannerReferenceView, CourseRatesView)

urlpatterns += [
    path("attendance/sessions/<uuid:session_id>/captures/", CaptureQueueView.as_view()),
    path("attendance/sessions/<uuid:session_id>/scanner-references/", ScannerReferenceView.as_view()),
    path("attendance/captures/<uuid:capture_id>/review/", CaptureReviewView.as_view()),
    path("attendance/captures/<uuid:capture_id>/resolve/", CaptureResolutionView.as_view()),
    path("attendance/offerings/<int:offering_id>/rates/", CourseRatesView.as_view()),
]

from .reconciliation_views import MeetingFinalisationView
urlpatterns += [
    path("attendance/sessions/<uuid:session_id>/finalisation/", MeetingFinalisationView.as_view()),
]

from .reconciliation_views import MeetingExcusalsView
urlpatterns += [
    path("attendance/sessions/<uuid:session_id>/excusals/", MeetingExcusalsView.as_view()),
]

from .policy_views import CourseEligibilityView, ExamExceptionView, MyEligibilityView, BiometricReferencesView
urlpatterns += [
    path("attendance/offerings/<int:offering_id>/eligibility/", CourseEligibilityView.as_view()),
    path("attendance/offerings/<int:offering_id>/exam-exceptions/", ExamExceptionView.as_view()),
    path("me/attendance-eligibility/", MyEligibilityView.as_view()),
    path("attendance/biometric-references/", BiometricReferencesView.as_view()),
]
from .policy_views import BiometricStudentsView
urlpatterns += [path("attendance/biometric-students/", BiometricStudentsView.as_view())]
