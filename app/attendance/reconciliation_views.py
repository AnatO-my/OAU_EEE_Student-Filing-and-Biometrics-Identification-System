"""Metadata-only review API; probe bytes are never exposed to browser clients."""
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from academics.models import CourseOffering
from academics.views import run_academic_service
from students.models import Student
from .models import PendingCaptureEvent
from .reconciliation import register_reference, open_review, resolve_capture, course_rates
from .views import StaffView, visible_sessions


def review_data(review):
    return {"capture_id": str(review.capture_id), "mode": review.mode, "state": review.state, "review_selected": True,
            "student_id": str(review.student_id) if review.student_id else None,
            "resolved_at": review.resolved_at, "reason": review.reason,
            "automatic_matching_available": False}


class ReviewSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["live", "deferred"])


class ResolutionSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    reason = serializers.CharField(max_length=1000)
    timing_confirmed = serializers.BooleanField()


class ReferenceSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    scanner_uuid = serializers.UUIDField()
    reference_id = serializers.CharField(max_length=100)


class CaptureQueueView(StaffView):
    @transaction.atomic
    def get(self, request, session_id):
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        from .services import require_course
        run_academic_service(require_course, user=request.user, offering=session.offering, action="import_pending_captures")
        from academics.views import ResultPagination
        rows = PendingCaptureEvent.objects.filter(batch__session=session).select_related("review").order_by("received_at", "pk")
        paginator = ResultPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response([
            review_data(row.review) if hasattr(row, "review") else
            {"capture_id": str(row.pk), "mode": "deferred", "state": "archived", "student_id": None, "review_selected": False,
             "automatic_matching_available": False}
            for row in page])


class CaptureReviewView(StaffView):
    def post(self, request, capture_id):
        capture = get_object_or_404(PendingCaptureEvent.objects.filter(batch__session__in=visible_sessions(request.user)), pk=capture_id)
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(review_data(run_academic_service(open_review, user=request.user, capture=capture, **serializer.validated_data)))


class CaptureResolutionView(StaffView):
    def post(self, request, capture_id):
        capture = get_object_or_404(PendingCaptureEvent.objects.filter(batch__session__in=visible_sessions(request.user)), pk=capture_id)
        serializer = ResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(review_data(run_academic_service(resolve_capture, user=request.user, capture=capture, **serializer.validated_data)))


class ScannerReferenceView(StaffView):
    def post(self, request, session_id):
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        serializer = ReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reference = run_academic_service(register_reference, user=request.user, session=session, **serializer.validated_data)
        return Response({"scanner_uuid": str(reference.scanner_uuid), "reference_id": reference.reference_id,
                         "student_id": str(reference.student_id), "identifier_value": reference.student.identifier_value,
                         "hardware_enrolment_performed": False})


class CourseRatesView(StaffView):
    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering.objects.select_related("academic_session"), pk=offering_id)
        return Response({"offering_id": offering.pk, "results": run_academic_service(course_rates, user=request.user, offering=offering)})


class FinalisationSerializer(serializers.Serializer):
    expected_digest = serializers.RegexField(regex=r"^[0-9a-f]{64}$")
    reviewed = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000)


class MeetingFinalisationView(StaffView):
    def get(self, request, session_id):
        from .finalisation import inspect_finalisation
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        return Response(run_academic_service(inspect_finalisation, user=request.user, session=session))

    def post(self, request, session_id):
        from .finalisation import finalise_meeting
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        serializer = FinalisationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(run_academic_service(finalise_meeting, user=request.user,
            session=session, **serializer.validated_data))


class ExcusalSerializer(serializers.Serializer):
    retrospective = serializers.BooleanField(default=False)
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    event_id = serializers.UUIDField()
    is_excused = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000)


class MeetingExcusalsView(StaffView):
    def get(self, request, session_id):
        from .finalisation import inspect_finalisation
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        state = run_academic_service(inspect_finalisation, user=request.user, session=session)
        return Response({"meeting_id": str(session.pk), "excusals": state["confirmed_excusals"]})

    def post(self, request, session_id):
        from .excusals import decide_excusal
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        serializer = ExcusalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action, replayed = run_academic_service(decide_excusal, user=request.user, session=session, **serializer.validated_data)
        return Response({"event_id": str(action.pk), "student_id": str(action.excusal.student_id),
            "is_excused": action.is_excused, "current_is_excused": action.excusal.is_excused,
            "previous_is_excused": action.previous_is_excused,
            "retrospective": action.excusal.retrospective,
            "historical_roster_member": not action.excusal.retrospective,
            "eligibility_roster_revision": action.eligibility_roster_revision,
            "reviewed_by": action.actor_id, "reviewed_at": action.created_at,
            "reason": action.reason, "replayed": replayed})
