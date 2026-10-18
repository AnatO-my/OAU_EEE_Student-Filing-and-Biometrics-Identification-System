"""Raw JSONL uploads with a fixed memory bound; no biometric responses."""
from django.db.models import Count
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, UnsupportedMediaType, ValidationError
from rest_framework.response import Response

from academics.views import ResultPagination
from .models import PendingCaptureBatch
from .pending_format import BatchFormatError, read_batch_stream
from .pending_services import PendingBatchConflict, import_pending_batch, preview_pending_batch
from .views import StaffView, visible_sessions


# Gate both upload and listing endpoints on the narrow capture-import capability.
class CanImportPendingCaptures(permissions.BasePermission):
    # Require active staff with the dedicated import permission at the API edge.
    def has_permission(self, request, view):
        user = request.user
        return (user.is_authenticated and user.is_active and user.is_staff
                and user.has_perm("attendance.import_pending_captures"))


# Return conflicts as HTTP 409 without reflecting submitted capture content.
class CaptureConflictResponse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Capture evidence conflicts with previously accepted data."


class CaptureSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        # Django's CSRF check looks for POST form fields before its header fallback.
        # On a DRF Request that invokes parsers, which this opaque JSONL endpoint
        # deliberately disables. The original HttpRequest has an empty form POST
        # for non-form content and checks the same cookie/header/origin normally,
        # leaving the raw stream unread until course authorization succeeds.
        return super().enforce_csrf(request._request)


# Centralize meeting visibility and bounded raw-body processing for these endpoints.
class PendingAccessView(StaffView):
    authentication_classes = [CaptureSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, CanImportPendingCaptures]
    # Read request.stream directly. Multipart/JSON parsing must not buffer a file
    # before our explicit byte bound or echo its contents in validation errors.
    parser_classes = []

    # Resolve only meetings visible to this staff user before reading request data.
    def session(self, request, session_id):
        return get_object_or_404(visible_sessions(request.user), pk=session_id)

    # Share bounded upload handling while separating preview from committed import.
    def process(self, request, session_id, *, commit):
        session = self.session(request, session_id)
        if request._request.content_type != "application/x-ndjson":
            raise UnsupportedMediaType(request.content_type)
        try:
            data = read_batch_stream(request.stream)
        except BatchFormatError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from None
        kwargs = {"user": request.user, "session": session, "data": data}
        if commit:
            kwargs["expected_sha256"] = request.headers.get("X-Capture-SHA256")
        try:
            result = (import_pending_batch if commit else preview_pending_batch)(**kwargs)
        except PendingBatchConflict as exc:
            raise CaptureConflictResponse({"non_field_errors": exc.messages}) from None
        except DjangoValidationError as exc:
            raise ValidationError({"non_field_errors": exc.messages}) from None
        code = status.HTTP_201_CREATED if commit and not result["replayed"] else status.HTTP_200_OK
        return Response(result, status=code)


# Expose the read-only preview operation for a pending capture snapshot.
class PendingBatchPreviewView(PendingAccessView):
    # Validate and summarize the submitted snapshot without persisting it.
    def post(self, request, session_id):
        return self.process(request, session_id, commit=False)


# Import snapshots and expose a paginated metadata-only batch list.
class PendingBatchesView(PendingAccessView):
    # Persist the exact snapshot only after the caller confirms its preview digest.
    def post(self, request, session_id):
        return self.process(request, session_id, commit=True)

    # List metadata and review flags only; biometric probes remain private.
    def get(self, request, session_id):
        session = self.session(request, session_id)
        rows = PendingCaptureBatch.objects.filter(session=session).annotate(event_count=Count("captures")).order_by("imported_at", "pk")
        paginator = ResultPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response([
            {"batch_id": str(batch.pk), "class_session_id": str(batch.session_id),
             "metadata": batch.metadata, "event_count": batch.event_count,
             "received_at": batch.imported_at, "state": "pending_review",
             "identity_review_required": True, "timing_review_required": True,
             "device_authenticated": False, "recovery_review_required": batch.recovery_review_required}
            for batch in page
        ])
