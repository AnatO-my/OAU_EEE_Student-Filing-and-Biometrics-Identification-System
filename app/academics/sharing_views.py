from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from students.models import Guardian
from .models import AcademicSession, CourseOffering, GuardianSharingPreference, ResultShareBatch
from .sharing import create_preview, queue_batch, set_preference, batch_data, retry_failed
from .views import IsActiveHOD, ResultPagination, run_academic_service


class PreviewSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    student_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    academic_session = serializers.PrimaryKeyRelatedField(queryset=AcademicSession.objects.all())
    semester = serializers.ChoiceField(choices=CourseOffering.Semester.choices)
    channels = serializers.ListField(child=serializers.ChoiceField(choices=["email", "whatsapp"]),
                                    min_length=1, max_length=2)

    def validate(self, attrs):
        for field in ("student_ids", "channels"):
            if len(attrs[field]) != len(set(attrs[field])):
                raise serializers.ValidationError({field: "Duplicate entries are not allowed."})
        return attrs


class QueueSerializer(serializers.Serializer):
    expected_digest = serializers.RegexField(r"^[a-f0-9]{64}$")


class PreferenceSerializer(serializers.Serializer):
    email_enabled = serializers.BooleanField()
    whatsapp_enabled = serializers.BooleanField()
    evidence = serializers.CharField(max_length=2000)


@method_decorator(never_cache, name="dispatch")
class HODSharingView(APIView):
    permission_classes = [IsActiveHOD]


class ResultSharePreviewView(HODSharingView):
    def post(self, request):
        serializer = PreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = run_academic_service(create_preview, user=request.user, **serializer.validated_data)
        return Response(batch_data(batch), status=status.HTTP_201_CREATED)


class ResultShareBatchView(HODSharingView):
    def get(self, request, batch_id):
        return Response(batch_data(get_object_or_404(ResultShareBatch, pk=batch_id)))


class ResultShareQueueView(HODSharingView):
    def post(self, request, batch_id):
        serializer = QueueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = run_academic_service(queue_batch, user=request.user,
            batch=get_object_or_404(ResultShareBatch, pk=batch_id), **serializer.validated_data)
        return Response(batch_data(batch), status=status.HTTP_202_ACCEPTED)


class ResultShareRetryView(HODSharingView):
    def post(self, request, batch_id):
        count = run_academic_service(retry_failed, user=request.user,
            batch=get_object_or_404(ResultShareBatch, pk=batch_id))
        return Response({"requeued": count}, status=status.HTTP_202_ACCEPTED)


class GuardianSharingPreferenceView(HODSharingView):
    def guardian(self, student_id, guardian_id):
        return get_object_or_404(Guardian, pk=guardian_id, student_id=student_id)

    def get(self, request, student_id, guardian_id):
        preference = GuardianSharingPreference.objects.filter(guardian=self.guardian(student_id, guardian_id)).first()
        return Response({"email_enabled": bool(preference and preference.email_enabled),
            "whatsapp_enabled": bool(preference and preference.whatsapp_enabled),
            "evidence": preference.evidence if preference else "",
            "updated_at": preference.updated_at if preference else None})

    def put(self, request, student_id, guardian_id):
        guardian = self.guardian(student_id, guardian_id)
        serializer = PreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(set_preference, user=request.user, guardian=guardian, **serializer.validated_data)
        return self.get(request, student_id, guardian_id)


class ResultShareListView(HODSharingView):
    def get(self, request):
        from collections import Counter
        paginator = ResultPagination()
        page = paginator.paginate_queryset(ResultShareBatch.objects.order_by("-created_at", "pk"), request)
        summaries = [{"id": str(batch.pk), "academic_session": batch.academic_session_id,
            "semester": batch.semester, "created_at": batch.created_at, "queued_at": batch.queued_at,
            "counts": dict(Counter(batch.deliveries.values_list("status", flat=True)))} for batch in page]
        return paginator.get_paginated_response(summaries)
