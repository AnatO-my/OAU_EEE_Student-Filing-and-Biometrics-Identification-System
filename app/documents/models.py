import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from students.models import Student

def private_storage():
    """Where files are saved. No public URL points here."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)

import os

def document_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".pdf", ".jpg", ".jpeg", ".png"}:
        extension = ""
    return f"documents/{instance.student_id}/{uuid.uuid4().hex}{extension}"

class StudentDocument(models.Model):
    class DocumentType(models.TextChoices):
        RESULT = "result", "Result"
        BIODATA = "biodata", "Biodata"
        BIRTH_CERTIFICATE = "birth_cecrtificate", "birth certificate"
        OTHER = "other", "other"
        CLEARANCE = "clearance", "Clearance certificate"
        JAMB = "jamb", "JAMB result"
        WAEC = "waec", "WAEC result"
        STATE_ORIGIN = "state_origin", "State of origin certificate"
    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        NEEDS_REVIEW = "needs_review", "Needs review"

    document_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
    )
    file = models.FileField(
        upload_to=document_upload_path,
        storage=private_storage,
    )
    original_filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEEDS_REVIEW,
    )
    approval_state = models.CharField(max_length=12, default="active", choices=[("active","Active"),("pending","Pending approval"),("archived","Archived"),("rejected","Rejected")])
    replaces = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="reviewed_documents")
    reviewed_at = models.DateTimeField(null=True)
    review_reason = models.CharField(max_length=1000, blank=True)
    ocr_text = models.TextField(blank=True)
    ocr_confidence = models.FloatField(null=True, blank=True)
    quality_notes = models.CharField(max_length=255, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document_type} for {self.student_id}"
