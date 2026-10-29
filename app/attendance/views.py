from django.db.models import F
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from academics.models import CourseOffering
from academics.current_session import current_session_name
from academics.views import IsActiveHOD, ResultPagination, run_academic_service
from students.models import Student
from .models import CourseStaffAssignment, CourseRoster, AttendanceSession, AttendanceRecord
from .services import assign_staff, confirm_roster, roster_candidates, open_session, close_session, record_manual, correct_record


# Limit session queries to current offerings assigned to authorized staff.
def visible_sessions(user):
    rows = AttendanceSession.objects.order_by("-starts_at", "pk")
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return rows.none()
    if user.is_superuser:
        return rows
    if not user.has_perm("attendance.view_attendance"):
        return rows.none()
    assignments = CourseStaffAssignment.objects.filter(staff=user, is_active=True,
        offering__academic_session__name=current_session_name()).values("offering_id")
    return rows.filter(offering_id__in=assignments)


# Expose session details without allowing clients to change them directly.
class SessionSerializer(serializers.ModelSerializer):
    # Configure the session response fields as read-only.
    class Meta:
        model = AttendanceSession
        fields = ["id", "offering", "title", "starts_at", "ends_at", "status", "roster_revision", "closed_at"]
        read_only_fields = fields


# Validate the offering and time window used when opening a session.
class SessionWriteSerializer(serializers.Serializer):
    offering = serializers.PrimaryKeyRelatedField(queryset=CourseOffering.objects.all())
    title = serializers.CharField(max_length=200)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


# Validate a proposed roster membership and its optimistic-lock revision.
class RosterSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=1000)
    expected_revision = serializers.IntegerField(min_value=0)


# Validate staff assignment changes made by the HOD.
class AssignmentSerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())
    is_active = serializers.BooleanField()


# Validate a student's manual attendance event and its idempotency key.
class ManualSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    event_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)


# Restrict attendance corrections to known statuses and a supplied reason.
class CorrectionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["present", "absent"])
    reason = serializers.CharField(max_length=1000)


# Require authentication for attendance API endpoints and disable response caching.
@method_decorator(never_cache, name="dispatch")
class StaffView(APIView):
    permission_classes = [permissions.IsAuthenticated]


# Let the HOD inspect candidate students and confirm the offering roster.
class RosterView(StaffView):
    permission_classes = [IsActiveHOD]

    # Return paginated candidate students alongside the current approval.
    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        roster = CourseRoster.objects.filter(offering=offering).first()
        candidates = roster_candidates(offering)
        paginator = ResultPagination()
        response = paginator.get_paginated_response(paginator.paginate_queryset(candidates, request))
        response.data.update({"confirmed_revision": roster.revision if roster else 0,
            "confirmed_student_ids": [str(pk) for pk in roster.students.values_list("pk", flat=True)] if roster else []})
        return response

    # Confirm a validated roster using its expected revision.
    def put(self, request, offering_id):
        serializer = RosterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roster = run_academic_service(confirm_roster, user=request.user,
            offering=get_object_or_404(CourseOffering, pk=offering_id), **serializer.validated_data)
        return Response({"revision": roster.revision, "student_ids": [str(pk) for pk in roster.students.values_list("pk", flat=True)]})


# Let the HOD activate or deactivate staff for one course offering.
class AssignmentView(StaffView):
    permission_classes = [IsActiveHOD]

    # Show existing active and inactive assignments without exposing private staff details.
    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        rows = CourseStaffAssignment.objects.filter(offering=offering).select_related("staff").order_by("staff__username", "pk")
        paginator = ResultPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response([
            {"id": row.pk, "staff": row.staff_id, "staff_username": row.staff.username,
             "staff_name": row.staff.get_full_name(), "staff_is_active": row.staff.is_active,
             "is_active": row.is_active} for row in page
        ])

    # Apply the validated assignment through the academic service boundary.
    def put(self, request, offering_id):
        serializer = AssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = run_academic_service(assign_staff, user=request.user,
            offering=get_object_or_404(CourseOffering, pk=offering_id), **serializer.validated_data)
        return Response({"id": assignment.pk, "staff": assignment.staff_id, "is_active": assignment.is_active})


# List visible sessions or open a new session for an assigned offering.
class SessionsView(StaffView):
    # Paginate only sessions the requesting staff member may see.
    def get(self, request):
        paginator = ResultPagination()
        return paginator.get_paginated_response(SessionSerializer(
            paginator.paginate_queryset(visible_sessions(request.user), request), many=True).data)

    # Validate and create a session through the authorized service.
    def post(self, request):
        serializer = SessionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = run_academic_service(open_session, user=request.user, **serializer.validated_data)
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


# Return one visible session together with its fixed roster snapshot.
class SessionView(StaffView):
    # Hide sessions outside the caller's visibility scope.
    def get(self, request, session_id):
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        roster = CourseRoster.objects.filter(offering=session.offering).first()
        fields = ("id", "full_name", "identifier_value")
        return Response({**SessionSerializer(session).data, "student_ids": session.student_ids,
            "student_details": list(Student.objects.filter(pk__in=session.student_ids).annotate(id=F("pk")).values(*fields)),
            "current_roster_students": list(roster.students.annotate(id=F("pk")).values(*fields)) if roster else []})


# Close a visible session through the audited service workflow.
class CloseView(StaffView):
    # Reuse the visibility scope before applying the close operation.
    def post(self, request, session_id):
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        session = run_academic_service(close_session, user=request.user, session=session)
        return Response(SessionSerializer(session).data)


# List session records or add an idempotent manual attendance event.
class RecordsView(StaffView):
    # Return student-sorted attendance records in paginated form.
    def get(self, request, session_id):
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        paginator = ResultPagination()
        rows = session.records.order_by("student_id")
        return paginator.get_paginated_response(list(paginator.paginate_queryset(rows.values(
            "id", "student_id", "status", "recorded_at", "recorded_by_id", "reason"), request)))

    # Record a validated manual event and distinguish retries from new events.
    def post(self, request, session_id):
        session = get_object_or_404(visible_sessions(request.user), pk=session_id)
        serializer = ManualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event, replayed = run_academic_service(record_manual, user=request.user,
            session=session, **serializer.validated_data)
        return Response({"event_id": str(event.pk), "duplicate": event.duplicate, "replayed": replayed},
            status=status.HTTP_200_OK if replayed or event.duplicate else status.HTTP_201_CREATED)


# Correct a record only when its session is visible to the requesting staff.
class CorrectionView(StaffView):
    # Validate the correction and persist it through the audit-aware service.
    def post(self, request, record_id):
        record = get_object_or_404(AttendanceRecord.objects.filter(session__in=visible_sessions(request.user)), pk=record_id)
        serializer = CorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = run_academic_service(correct_record, user=request.user, record=record, **serializer.validated_data)
        return Response({"id": record.pk, "status": record.status})


# Let an authenticated student retrieve only their own attendance history.
class MyAttendanceView(StaffView):
    # Resolve the requester's student profile and paginate its records.
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        paginator = ResultPagination()
        rows = AttendanceRecord.objects.filter(student=student).order_by("-recorded_at")
        return paginator.get_paginated_response(list(paginator.paginate_queryset(rows.values(
            "id", "session_id", "session__offering_id", "status", "recorded_at"), request)))
