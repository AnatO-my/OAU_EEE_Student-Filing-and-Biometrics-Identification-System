import uuid
from django.conf import settings
from django.db import models
from documents.models import private_storage


def material_path(instance, filename):
    return f"teaching-materials/{instance.material_id}/{uuid.uuid4().hex}"


class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        default_permissions = ()
        permissions = [("publish_message", "Can directly publish departmental messages")]


class MessageVersion(models.Model):
    message = models.ForeignKey(Announcement, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    event_id = models.UUIDField(unique=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.JSONField()
    withdrawn = models.BooleanField(default=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["message", "version"], name="unique_teaching_message_version")]


class MessageReceipt(models.Model):
    version = models.ForeignKey(MessageVersion, on_delete=models.PROTECT, related_name="receipts")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    read_at = models.DateTimeField(null=True)
    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["version", "recipient"], name="unique_teaching_message_receipt")]


class Notification(models.Model):
    receipt = models.OneToOneField(MessageReceipt, on_delete=models.PROTECT)
    destination = models.EmailField()
    state = models.CharField(max_length=12, default="pending", choices=[("pending","Pending"),("sending","Sending"),("sent","Sent"),("unknown","Unknown"),("skipped","Skipped")])
    attempted_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)
    class Meta:
        default_permissions = ()


class Material(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        default_permissions = ()
        permissions = [("manage_material", "Can upload and maintain assigned course materials")]


class MaterialVersion(models.Model):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    event_id = models.UUIDField(unique=True)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=material_path, storage=private_storage, blank=True)
    filename = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    withdrawn = models.BooleanField(default=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["material", "version"], name="unique_teaching_material_version")]


class TimetableEntry(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    venue = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    class Meta:
        default_permissions = ()
        permissions = [("manage_timetable", "Can maintain assigned course timetable entries")]


class TimetableRevision(models.Model):
    entry = models.ForeignKey(TimetableEntry, on_delete=models.PROTECT, related_name="revisions")
    event_id = models.UUIDField(unique=True)
    snapshot = models.JSONField()
    clash_ids = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        default_permissions = ()
