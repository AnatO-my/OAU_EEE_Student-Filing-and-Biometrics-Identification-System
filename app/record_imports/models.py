import uuid

from django.conf import settings
from django.db import models


class ImportMutex(models.Model):
    """Serialize reviewed imports; normal record services retain their own locks."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_record_import_mutex")]


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_id = models.UUIDField()
    kind = models.CharField(max_length=10, choices=[("roster", "Roster"), ("results", "Results")])
    filename = models.CharField(max_length=120)
    file_sha256 = models.CharField(max_length=64)
    source_csv = models.TextField()
    parsed_rows = models.JSONField()
    source_context = models.JSONField(default=dict)
    preview = models.JSONField()
    preview_digest = models.CharField(max_length=64)
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=12, default="preview")
    receipt = models.JSONField(null=True)
    commit_request = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    committed_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["owner", "request_id"], name="unique_record_import_request")]


class ImportChange(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="changes")
    row_number = models.PositiveIntegerField()
    action = models.CharField(max_length=20)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    result = models.ForeignKey("academics.Result", on_delete=models.PROTECT, null=True)
    before = models.JSONField()
    after = models.JSONField()
    reason = models.CharField(max_length=1000, blank=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["batch", "row_number"], name="unique_record_import_change_row")]


class SourcePerformance(models.Model):
    """Immutable reported figures and comparison evidence, never replacement results."""
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="source_performances")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="source_performances")
    academic_session = models.ForeignKey("academics.AcademicSession", on_delete=models.PROTECT)
    semester = models.CharField(max_length=10)
    source = models.JSONField()
    comparison_at_import = models.JSONField()
    review_status = models.CharField(max_length=20, default="unresolved")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["batch", "student", "academic_session", "semester"],
            name="unique_import_source_performance")]
