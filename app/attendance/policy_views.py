from django.db.models import F
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from academics.models import CourseOffering
from academics.views import run_academic_service
from students.models import Student
from students.services import students_visible_to
from academics.current_session import current_session_name
from .views import StaffView
from .models import ScannerReference, CourseRoster, AttendanceSession, AttendancePolicyRevision
from . import policy


class PolicySerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    minimum_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    reason = serializers.CharField(max_length=1000)


class ExceptionSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    enabled = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000)


class CourseEligibilityView(StaffView):
    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering.objects.select_related("academic_session"), pk=offering_id)
        rows = run_academic_service(policy.eligibility, user=request.user, offering=offering)
        students = {str(row.pk): row for row in Student.objects.filter(pk__in=[item["student_id"] for item in rows])}
        for row in rows:
            student = students.get(row["student_id"])
            row.update({"full_name": student.full_name if student else "", "identifier_value": student.identifier_value if student else ""})
        return Response(rows)
    def put(self, request, offering_id):
        serializer = PolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = run_academic_service(policy.set_policy, user=request.user,
            offering=get_object_or_404(CourseOffering.objects.select_related("academic_session"), pk=offering_id), **serializer.validated_data)
        return Response({"revision": row.pk, "minimum_percentage": str(row.minimum_percentage), "reason": row.reason})


class ExamExceptionView(StaffView):
    def post(self, request, offering_id):
        serializer = ExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = run_academic_service(policy.exam_exception, user=request.user,
            offering=get_object_or_404(CourseOffering.objects.select_related("academic_session"), pk=offering_id), **serializer.validated_data)
        return Response({"event_id": row.event_id, "student_id": row.student_id, "enabled": row.enabled, "reason": row.reason})


class MyEligibilityView(StaffView):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        offerings = set(CourseRoster.objects.filter(students=student).values_list("offering_id", flat=True))
        offerings.update(session.offering_id for session in AttendanceSession.objects.all() if str(student.pk) in session.student_ids)
        result = []
        for offering in CourseOffering.objects.filter(pk__in=offerings).select_related("academic_session", "course"):
            rows = policy.eligibility(user=request.user, offering=offering, student=student)
            own = next((row for row in rows if row["student_id"] == str(student.pk)), None)
            if own:
                result.append({**own, "offering_id": offering.pk, "course": offering.course.code})
        return Response(result)


class ReferenceSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    scanner_uuid = serializers.UUIDField()
    reference_id = serializers.CharField(max_length=100)
    replaces = serializers.PrimaryKeyRelatedField(queryset=ScannerReference.objects.all(), required=False, allow_null=True)


class BiometricReferencesView(StaffView):
    def get(self, request):
        from django.core.exceptions import PermissionDenied
        if not request.user.is_staff or not request.user.has_perm("attendance.manage_biometric_reference"):
            raise PermissionDenied("Authorised biometric enrolment staff access is required.")
        students = policy.biometric_students(request.user)
        rows = ScannerReference.objects.filter(student__in=students).order_by("student_id", "-registered_at")
        return Response([{ "id": row.pk, "student_id": str(row.student_id), "scanner_uuid": str(row.scanner_uuid),
            "reference_id": row.reference_id, "is_active": row.is_active, "replaces": row.replaces_id,
            "disabled_at": row.disabled_at, "hardware_enrolment_performed": False} for row in rows])
    def post(self, request):
        serializer = ReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = run_academic_service(policy.enrol_reference, user=request.user, **serializer.validated_data)
        return Response({"id": row.pk, "student_id": str(row.student_id), "is_active": row.is_active,
            "replaces": row.replaces_id, "hardware_enrolment_performed": False})


class BiometricStudentsView(StaffView):
    def get(self, request):
        from django.core.exceptions import PermissionDenied
        if not request.user.is_staff or not request.user.has_perm("attendance.manage_biometric_reference"):
            raise PermissionDenied("Authorised biometric enrolment staff access is required.")
        return Response(list(policy.biometric_students(request.user).order_by("full_name", "pk").annotate(id=F("pk")).values("id", "full_name", "identifier_value")))
