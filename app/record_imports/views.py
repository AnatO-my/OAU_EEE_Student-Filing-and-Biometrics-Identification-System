import json
import io

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import permissions, serializers
from rest_framework.exceptions import APIException, ParseError, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import BaseParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .format import MAX_BYTES
from .models import ImportBatch
from .services import ImportConflict, commit_import, create_preview, fresh_user, public_batch, refresh_preview, require_batch_access
from .services import require_access
from .preparation import PreparationError, prepare_source


class BoundedMultipartParser(MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        maximum = MAX_BYTES + 65536
        raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ParseError("Upload one source file of at most 2 MiB.")
        return super().parse(io.BytesIO(raw), media_type=media_type, parser_context=parser_context)


class PrepareInput(serializers.Serializer):
    file = serializers.FileField(max_length=500)
    attempt_number = serializers.IntegerField(required=False, min_value=1, max_value=32767, allow_null=True)
    academic_session = serializers.CharField(required=False, allow_blank=True, default="", max_length=9)
    semester = serializers.ChoiceField(choices=["", "harmattan", "rain"], required=False, default="")
    include_reviewed_zero_scores = serializers.BooleanField(required=False, default=False)
    strategy = serializers.ChoiceField(choices=["lines", "text"], required=False, default="lines")


class PrepareView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    parser_classes = [BoundedMultipartParser]

    def post(self, request):
        # Conversion is results-only. Check active permissions and adviser scope
        # before reading file contents or starting the PDF extraction process.
        from academics.session_context import current_session_name
        from accounts.models import AdviserAssignment
        user = fresh_user(request.user)
        require_access(user, "results")
        if not user.is_superuser and not AdviserAssignment.objects.filter(staff=user,
                academic_session=current_session_name(), is_active=True).exists():
            raise PermissionDenied("An active adviser assignment is required to prepare result imports.")
        if hasattr(request.data, "getlist") and len(request.data.getlist("file")) != 1:
            raise ValidationError("Upload exactly one PDF or CSV source file.")
        serializer = PrepareInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        options = dict(serializer.validated_data)
        upload = options.pop("file")
        if upload.size > MAX_BYTES:
            raise ValidationError("Upload a source file of at most 2 MiB.")
        data = upload.read(MAX_BYTES + 1)
        try:
            result = prepare_source(data, upload.name, **options)
        except PreparationError as error:
            raise ValidationError({"non_field_errors": [str(error)]}) from None
        response = Response(result)
        response["Cache-Control"] = "no-store, private"
        return response


class BoundedJSONParser(BaseParser):
    media_type = "application/json"

    def parse(self, stream, media_type=None, parser_context=None):
        # Bound input before json.loads, including chunked requests without a
        # Content-Length. Source CSV has a separate exact UTF-8 byte bound.
        maximum = MAX_BYTES * 2 + 65536
        body = stream.read(maximum + 1)
        if len(body) > maximum:
            raise ParseError("The import request exceeds the upload limit.")
        try:
            return json.loads(body.decode("utf-8", "strict"))
        except (UnicodeError, ValueError, RecursionError):
            raise ParseError("Send a valid UTF-8 JSON import request.") from None


class PreviewInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["roster", "results"])
    request_id = serializers.UUIDField()
    filename = serializers.CharField(max_length=500)
    csv_text = serializers.CharField(trim_whitespace=False)
    source_context = serializers.JSONField(required=False, default=dict)


class CommitInput(serializers.Serializer):
    preview_digest = serializers.RegexField(regex=r"^[0-9a-f]{64}$")
    correction_approvals = serializers.ListField(required=False, default=list, max_length=1000)


class ConflictResponse(APIException):
    status_code = 409
    default_detail = "Refresh and review the import before committing."


def invoke(action, **kwargs):
    try:
        return action(**kwargs)
    except ImportBatch.DoesNotExist:
        raise Http404 from None
    except ImportConflict as error:
        raise ConflictResponse({"non_field_errors": error.messages}) from None
    except DjangoValidationError as error:
        raise ValidationError({"non_field_errors": error.messages}) from None


class StaffImportView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    parser_classes = [BoundedJSONParser]


class PreviewView(StaffImportView):
    def post(self, request):
        serializer = PreviewInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch, replayed = invoke(create_preview, user=request.user, **serializer.validated_data)
        return Response(public_batch(batch), status=200 if replayed else 201)


class DetailView(StaffImportView):
    def get(self, request, batch_id):
        user = fresh_user(request.user)
        try:
            batch = ImportBatch.objects.get(pk=batch_id, owner=user)
        except ImportBatch.DoesNotExist:
            raise Http404 from None
        require_batch_access(user, batch)
        return Response(public_batch(batch))


class RefreshView(StaffImportView):
    def post(self, request, batch_id):
        batch = invoke(refresh_preview, user=request.user, batch_id=batch_id)
        return Response(public_batch(batch))


class CommitView(StaffImportView):
    def post(self, request, batch_id):
        serializer = CommitInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch, replayed = invoke(commit_import, user=request.user, batch_id=batch_id, **serializer.validated_data)
        return Response(public_batch(batch), status=200 if replayed else 201)


class HistoryView(StaffImportView):
    def get(self, request):
        user = fresh_user(request.user)
        if not user.is_active or not user.is_staff or not user.has_perm("students.view_student"):
            raise PermissionDenied("You do not have permission to view import history.")
        kind = request.query_params.get("kind")
        if kind is not None and kind not in {"results", "roster"}:
            raise ValidationError({"kind": ["Choose results or roster."]})
        history = ImportBatch.objects.filter(owner=user)
        if kind is not None:
            history = history.filter(kind=kind)
        paginator = PageNumberPagination()
        paginator.page_size = 20
        rows = paginator.paginate_queryset(history, request)
        return paginator.get_paginated_response([
            {"id": str(batch.pk), "request_id": str(batch.request_id), "kind": batch.kind,
             "filename": batch.filename, "status": batch.status, "revision": batch.revision,
             "created_at": batch.created_at.isoformat(), "summary": batch.preview["summary"]}
            for batch in rows
        ])
