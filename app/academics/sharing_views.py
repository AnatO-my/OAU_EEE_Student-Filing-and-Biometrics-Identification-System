from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponse
from .sharing_pdf import snapshot_bytes
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from students.models import Guardian
from .models import AcademicSession, CourseOffering, GuardianSharingPreference, ResultShareBatch
from .sharing import create_preview, queue_batch, set_preference, batch_data, retry_failed
from .views import IsActiveHOD, ResultPagination, run_academic_service


# Validate the unique students, session, semester, and channels in a preview request.
class PreviewSerializer(serializers.Serializer):
    is_revised = serializers.BooleanField(default=False)
    revision_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    request_id = serializers.UUIDField()
    student_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    academic_session = serializers.PrimaryKeyRelatedField(queryset=AcademicSession.objects.all())
    semester = serializers.ChoiceField(choices=CourseOffering.Semester.choices)
    channels = serializers.ListField(child=serializers.ChoiceField(choices=["email", "whatsapp"]),
                                    min_length=1, max_length=2)

    # Reject repeated student or channel values before a batch can be created.
    def validate(self, attrs):
        for field in ("student_ids", "channels"):
            if len(attrs[field]) != len(set(attrs[field])):
                raise serializers.ValidationError({field: "Duplicate entries are not allowed."})
        return attrs


# Require the preview fingerprint that the HOD reviewed before queuing.
class QueueSerializer(serializers.Serializer):
    expected_digest = serializers.RegexField(r"^[a-f0-9]{64}$")


# Validate channel permissions and the evidence supporting a guardian's preference.
class PreferenceSerializer(serializers.Serializer):
    email_enabled = serializers.BooleanField()
    whatsapp_enabled = serializers.BooleanField()
    evidence = serializers.CharField(max_length=2000)


@method_decorator(never_cache, name="dispatch")
# Share HOD authorization and no-cache behavior across result-sharing endpoints.
class HODSharingView(APIView):
    permission_classes = [IsActiveHOD]


# Create and return a reviewed delivery preview without sending reports.
class ResultSharePreviewView(HODSharingView):
    # Validate the request and persist an idempotent preview batch.
    def post(self, request):
        serializer = PreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = run_academic_service(create_preview, user=request.user, **serializer.validated_data)
        return Response(batch_data(batch), status=status.HTTP_201_CREATED)


# Return the saved preview and delivery state for a batch.
class ResultShareBatchView(HODSharingView):
    # Load and serialize the requested batch.
    def get(self, request, batch_id):
        return Response(batch_data(get_object_or_404(ResultShareBatch, pk=batch_id)))


# Queue eligible deliveries after confirming the reviewed preview digest.
class ResultShareQueueView(HODSharingView):
    # Validate the digest and move eligible draft rows to the durable queue.
    def post(self, request, batch_id):
        serializer = QueueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = run_academic_service(queue_batch, user=request.user,
            batch=get_object_or_404(ResultShareBatch, pk=batch_id), **serializer.validated_data)
        return Response(batch_data(batch), status=status.HTTP_202_ACCEPTED)


# Retry eligible, definitively failed deliveries in a batch.
class ResultShareRetryView(HODSharingView):
    # Requeue only deliveries permitted by the service's retry policy.
    def post(self, request, batch_id):
        count = run_academic_service(retry_failed, user=request.user,
            batch=get_object_or_404(ResultShareBatch, pk=batch_id))
        return Response({"requeued": count}, status=status.HTTP_202_ACCEPTED)


# Read or update one guardian's documented result-sharing permissions.
class GuardianSharingPreferenceView(HODSharingView):
    # Resolve a guardian only when it belongs to the student in the route.
    def guardian(self, student_id, guardian_id):
        return get_object_or_404(Guardian, pk=guardian_id, student_id=student_id)

    # Return the guardian's stored permissions or safe defaults when none exist.
    def get(self, request, student_id, guardian_id):
        preference = GuardianSharingPreference.objects.filter(guardian=self.guardian(student_id, guardian_id)).first()
        return Response({"email_enabled": bool(preference and preference.email_enabled),
            "whatsapp_enabled": bool(preference and preference.whatsapp_enabled),
            "evidence": preference.evidence if preference else "",
            "updated_at": preference.updated_at if preference else None})

    # Validate and record new permissions, then return the persisted preference.
    def put(self, request, student_id, guardian_id):
        guardian = self.guardian(student_id, guardian_id)
        serializer = PreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(set_preference, user=request.user, guardian=guardian, **serializer.validated_data)
        return self.get(request, student_id, guardian_id)


# Provide a paginated history of batches with per-status delivery counts.
class ResultShareListView(HODSharingView):
    # Return batch summaries without exposing message contents in the list view.
    def get(self, request):
        from collections import Counter
        paginator = ResultPagination()
        page = paginator.paginate_queryset(ResultShareBatch.objects.order_by("-created_at", "pk"), request)
        summaries = [{"id": str(batch.pk), "academic_session": batch.academic_session_id,
            "semester": batch.semester, "created_at": batch.created_at, "queued_at": batch.queued_at,
            "counts": dict(Counter(batch.deliveries.values_list("status", flat=True)))} for batch in page]
        return paginator.get_paginated_response(summaries)


class ResultSharePDFView(HODSharingView):
    """Return only the exact PDF saved in this HOD-reviewed student snapshot."""
    def get(self, request, batch_id, student_id):
        batch = get_object_or_404(ResultShareBatch, pk=batch_id)
        item = next((row for row in batch.preview if row["student_id"] == str(student_id)), None)
        snapshot = ((item or {}).get("report") or {}).get("pdf")
        if not snapshot:
            raise Http404
        content = run_academic_service(snapshot_bytes, snapshot=snapshot)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{snapshot["filename"]}"'
        return response
