from django.urls import path

from .views import (
    ResultCreateView,
    ResultScoreUpdateView,
    ResultVerifyView,
    StudentGPAView,
    CourseRequirementListCreateView, CourseRequirementDetailView, GraduationReviewView,
    GradingScaleListCreateView, GradingScaleDetailView, GradingScalePublishView, OfferingScaleUpdateView,
    StudentCGPAView,
    MyGPAView,
    MyCGPAView,
    MyResultsView,
    MyResultDetailView,
    AcademicSessionListCreateView,
    CourseListCreateView,
    CourseOfferingListCreateView,
)

urlpatterns = [
    path(
        "results/",
        ResultCreateView.as_view(),
        name="result-create",
    ),
    path(
        "results/<int:result_id>/",
        ResultScoreUpdateView.as_view(),
        name="result-score-update",
    ),
    path(
        "results/<int:result_id>/verify/",
        ResultVerifyView.as_view(),
        name="result-verify",
    ),
    path(
        "students/<uuid:student_id>/gpa/",
        StudentGPAView.as_view(),
        name="student-gpa",
    ),
    path(
        "students/<uuid:student_id>/cgpa/",
        StudentCGPAView.as_view(),
        name="student-cgpa",
    ),
    path("me/gpa/", MyGPAView.as_view(), name="my-gpa"),
    path("me/cgpa/", MyCGPAView.as_view(), name="my-cgpa"),
    path("me/results/", MyResultsView.as_view(), name="my-results"),
    path(
        "me/results/<int:result_id>/",
        MyResultDetailView.as_view(),
        name="my-result-detail",
    ),
    path(
        "academic-sessions/",
        AcademicSessionListCreateView.as_view(),
        name="academic-session-list",
    ),
    path("courses/", CourseListCreateView.as_view(), name="course-list"),
    path(
        "course-offerings/",
        CourseOfferingListCreateView.as_view(),
        name="course-offering-list",
    ),
]

urlpatterns += [
    path("grading-scales/", GradingScaleListCreateView.as_view(), name="grading-scale-list"),
    path("grading-scales/<int:scale_id>/", GradingScaleDetailView.as_view(), name="grading-scale-detail"),
    path("grading-scales/<int:scale_id>/publish/", GradingScalePublishView.as_view(), name="grading-scale-publish"),
    path("course-offerings/<int:offering_id>/grading-scale/", OfferingScaleUpdateView.as_view(), name="offering-grading-scale"),
]

urlpatterns += [
    path("students/<uuid:student_id>/course-requirements/", CourseRequirementListCreateView.as_view(), name="course-requirement-list"),
    path("students/<uuid:student_id>/course-requirements/<int:requirement_id>/", CourseRequirementDetailView.as_view(), name="course-requirement-detail"),
    path("students/<uuid:student_id>/graduation-review/", GraduationReviewView.as_view(), name="graduation-review"),
]


from .sharing_views import (ResultSharePreviewView, ResultShareBatchView,
    ResultShareQueueView, ResultShareRetryView, GuardianSharingPreferenceView, ResultShareListView)

urlpatterns += [
    path("result-shares/preview/", ResultSharePreviewView.as_view(), name="result-share-preview"),
    path("result-shares/<uuid:batch_id>/", ResultShareBatchView.as_view(), name="result-share-detail"),
    path("result-shares/<uuid:batch_id>/send/", ResultShareQueueView.as_view(), name="result-share-send"),
    path("result-shares/<uuid:batch_id>/retry/", ResultShareRetryView.as_view(), name="result-share-retry"),
    path("students/<uuid:student_id>/guardians/<uuid:guardian_id>/result-sharing/",
         GuardianSharingPreferenceView.as_view(), name="guardian-result-sharing"),
]

urlpatterns += [path("result-shares/", ResultShareListView.as_view(), name="result-share-list")]
