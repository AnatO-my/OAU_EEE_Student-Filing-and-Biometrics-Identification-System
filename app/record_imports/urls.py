from django.urls import path
from .views import CommitView, DetailView, HistoryView, PrepareView, PreviewView, RefreshView

urlpatterns = [
    path("imports/", HistoryView.as_view(), name="record-import-history"),
    path("imports/prepare/", PrepareView.as_view(), name="record-import-prepare"),
    path("imports/previews/", PreviewView.as_view(), name="record-import-preview"),
    path("imports/<uuid:batch_id>/", DetailView.as_view(), name="record-import-detail"),
    path("imports/<uuid:batch_id>/refresh/", RefreshView.as_view(), name="record-import-refresh"),
    path("imports/<uuid:batch_id>/commit/", CommitView.as_view(), name="record-import-commit"),
]
