from django.db.models import F
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from rest_framework import serializers
from rest_framework.response import Response
from attendance.views import StaffView
from academics.models import CourseOffering
from academics.views import run_academic_service
from .models import Announcement, MessageVersion, MessageReceipt, Material, MaterialVersion, TimetableEntry
from . import services


class AudienceSerializer(serializers.Serializer):
    students = serializers.BooleanField(default=False)
    staff = serializers.BooleanField(default=False)
    student_ids = serializers.ListField(child=serializers.UUIDField(), max_length=1000, required=False)
    staff_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=1000, required=False)
    level = serializers.IntegerField(min_value=1, required=False)
    offering_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, required=False)
    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        if "student_ids" in result:
            result["student_ids"] = [str(pk) for pk in result["student_ids"]]
        return result


class PublicationSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=20000, required=False, allow_blank=True, default="")
    audience = AudienceSerializer()
    expected_version = serializers.IntegerField(min_value=0, default=0)
    withdrawn = serializers.BooleanField(default=False)


def message_data(version, user, include_body=False):
    own = version.message.sender_id == user.pk
    receipt = version.receipts.filter(recipient=user).first()
    data = {"id": str(version.message_id), "version": version.version, "subject": version.subject,
        "withdrawn": version.withdrawn, "created_at": version.created_at, "is_sender": own,
        "read_at": receipt.read_at if receipt else None}
    if include_body:
        data["body"] = "" if version.withdrawn else version.body
    if own:
        data.update({"audience": version.audience, "recipient_count": version.receipts.count(),
            "read_count": version.receipts.filter(read_at__isnull=False).count()})
    return data


class CoursesView(StaffView):
    def get(self, request):
        rows = []
        for offering in CourseOffering.objects.select_related("course", "academic_session").order_by("course__code", "pk"):
            try:
                services.course_access(request.user, offering)
            except PermissionDenied:
                continue
            rows.append({"id": offering.pk, "course": offering.course.code, "level": offering.level,
                "session": offering.academic_session.name, "semester": offering.semester})
        return Response(rows)


class MessagesView(StaffView):
    def get(self, request):
        rows = []
        messages = Announcement.objects.filter(sender=request.user) | Announcement.objects.filter(versions__receipts__recipient=request.user)
        for message in messages.distinct().order_by("-created_at"):
            version = message.versions.order_by("-version").first()
            if message.sender_id == request.user.pk or version.receipts.filter(recipient=request.user).exists():
                rows.append(message_data(version, request.user))
        return Response(rows)

    def post(self, request):
        serializer = PublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = run_academic_service(services.publish, user=request.user, **serializer.validated_data)
        return Response(message_data(version, request.user, True), status=201)


class MessageView(StaffView):
    def get(self, request, message_id):
        version = run_academic_service(services.open_message, user=request.user,
            message=get_object_or_404(Announcement, pk=message_id))
        return Response(message_data(version, request.user, True))

    def put(self, request, message_id):
        serializer = PublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = run_academic_service(services.publish, user=request.user,
            message=get_object_or_404(Announcement, pk=message_id), **serializer.validated_data)
        return Response(message_data(version, request.user, True))


class MessageHistoryView(StaffView):
    def get(self, request, message_id):
        message = get_object_or_404(Announcement, pk=message_id, sender=request.user)
        services.staff(request.user, "publish_message")
        return Response([{**message_data(version, request.user, True),
            "receipts": list(version.receipts.values("recipient_id", "read_at")),
            "notifications": list(version.receipts.values("recipient_id", "notification__state"))}
            for version in message.versions.order_by("version")])


class MaterialSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    offering = serializers.PrimaryKeyRelatedField(queryset=CourseOffering.objects.select_related("academic_session"))
    title = serializers.CharField(max_length=200)
    reason = serializers.CharField(max_length=1000)
    upload = serializers.FileField(required=False)
    expected_version = serializers.IntegerField(default=0, min_value=0)
    withdrawn = serializers.BooleanField(default=False)


def material_data(version):
    return {"id": str(version.material_id), "offering": version.material.offering_id,
        "title": version.title, "version": version.version, "filename": version.filename,
        "withdrawn": version.withdrawn, "created_at": version.created_at,
        "download_url": None if version.withdrawn else f"/api/teaching/materials/{version.material_id}/versions/{version.version}/download/"}


class MaterialsView(StaffView):
    def get(self, request):
        rows = []
        for material in Material.objects.select_related("offering__academic_session").order_by("pk"):
            try:
                services.course_access(request.user, material.offering)
            except PermissionDenied:
                continue
            rows.append(material_data(material.versions.order_by("-version").first()))
        return Response(rows)
    def post(self, request):
        serializer = MaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(material_data(run_academic_service(services.save_material, user=request.user, **serializer.validated_data)), status=201)


class MaterialView(StaffView):
    def put(self, request, material_id):
        serializer = MaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(material_data(run_academic_service(services.save_material, user=request.user,
            material=get_object_or_404(Material, pk=material_id), **serializer.validated_data)))
    def get(self, request, material_id):
        material = get_object_or_404(Material.objects.select_related("offering__academic_session"), pk=material_id)
        services.course_access(request.user, material.offering, "manage_material")
        return Response([material_data(row) for row in material.versions.order_by("version")])


class MaterialDownloadView(StaffView):
    def get(self, request, material_id, version):
        material = get_object_or_404(Material.objects.select_related("offering__academic_session"), pk=material_id)
        services.course_access(request.user, material.offering)
        row = get_object_or_404(material.versions, version=version, withdrawn=False)
        latest = material.versions.order_by("-version").first()
        if not request.user.is_staff and latest.pk != row.pk:
            raise PermissionDenied("Only the current course material may be downloaded by students.")
        return FileResponse(row.file.open("rb"), as_attachment=True, filename=row.filename,
            content_type="application/octet-stream")


class TimetableSerializer(serializers.Serializer):
    offering = serializers.PrimaryKeyRelatedField(queryset=CourseOffering.objects.select_related("academic_session"))
    event_id = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    venue = serializers.CharField(max_length=200)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    active = serializers.BooleanField(default=True)
    reason = serializers.CharField(max_length=1000)
    expected_revision = serializers.IntegerField(default=0, min_value=0)


def timetable_data(entry):
    return {"id": entry.pk, "offering": entry.offering_id, "title": entry.title, "venue": entry.venue,
        "starts_at": entry.starts_at, "ends_at": entry.ends_at, "active": entry.active,
        "revision": entry.revisions.count(), "clash_ids": services.clashes(entry),
        "warning": "Student timetable overlap: review the conflicting course entries." if services.clashes(entry) else None}


class TimetableView(StaffView):
    def get(self, request):
        rows = []
        for entry in TimetableEntry.objects.select_related("offering__academic_session").order_by("starts_at", "pk"):
            try:
                services.course_access(request.user, entry.offering)
            except PermissionDenied:
                continue
            if entry.active or request.user.is_staff:
                rows.append(timetable_data(entry))
        return Response(rows)
    def post(self, request):
        serializer = TimetableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = run_academic_service(services.save_timetable, user=request.user, **serializer.validated_data)
        return Response(timetable_data(entry), status=201)


class TimetableEntryView(StaffView):
    def put(self, request, entry_id):
        serializer = TimetableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = run_academic_service(services.save_timetable, user=request.user,
            entry=get_object_or_404(TimetableEntry, pk=entry_id), **serializer.validated_data)
        return Response(timetable_data(entry))


class AudienceOptionsView(StaffView):
    def get(self, request):
        from django.contrib.auth import get_user_model
        from students.models import Student
        services.staff(request.user, "publish_message")
        return Response({
            "students": list(Student.objects.filter(is_active=True, user__is_active=True).order_by("full_name", "pk").annotate(id=F("pk")).values("id", "full_name", "identifier_value", "current_level", "user_id")),
            "staff": [{"id": account.pk, "full_name": account.get_full_name() or account.username}
                      for account in get_user_model().objects.filter(is_active=True, is_staff=True).order_by("first_name", "username")]
        })
