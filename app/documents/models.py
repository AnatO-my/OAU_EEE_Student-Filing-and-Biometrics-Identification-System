import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from students.models import Student

def private_storage():
    """Where files are saved. No public URL points here."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)

def document_upload_path(instance, filename):
    # The server picks the file name, never the user. A malicious name
    # like "../../x.pdf" then cannot choose where the file lands.
    return f"documents/{instance.student_id}/{uuid.uuid4().hex}.pdf"

class StudentsDocument(models.Model):
    class DpcumentType(models.TextChoices):
        RESULT = "result", "Result"
        OTHER = "other", "other"

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
        choices=DpcumentType.choices,
        default=DpcumentType.RESULT,
    )
    file = models.FileField(
        upload_to=document_upload_path,
        storage=private_storage,
    )
    original_filename = models.CharField(max_length=255)
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
