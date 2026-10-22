from django.urls import path

from .admin_views import (AdministrationOptionsView, AdviserAssignmentDetailView,
    AdviserAssignmentListView, HODTransferView, StaffDetailView, StaffListView)

urlpatterns = [
    path("accounts/administration-options/", AdministrationOptionsView.as_view(), name="account-administration-options"),
    path("accounts/staff/", StaffListView.as_view(), name="account-staff-list"),
    path("accounts/staff/<int:staff_id>/", StaffDetailView.as_view(), name="account-staff-detail"),
    path("accounts/adviser-assignments/", AdviserAssignmentListView.as_view(), name="account-adviser-list"),
    path("accounts/adviser-assignments/<int:assignment_id>/", AdviserAssignmentDetailView.as_view(), name="account-adviser-detail"),
    path("accounts/transfer-hod/", HODTransferView.as_view(), name="account-transfer-hod"),
]
