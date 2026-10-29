import uuid
from django.conf import settings
from django.db import models


# Link staff to course offerings and track whether each assignment is active.
class CourseStaffAssignment(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    # Allow only one staff-assignment row for each offering and staff member.
    class Meta:
        constraints = [models.UniqueConstraint(fields=["offering", "staff"], name="unique_attendance_course_staff")]


# Store the currently confirmed student membership for a course offering.
class CourseRoster(models.Model):
    offering = models.OneToOneField("academics.CourseOffering", on_delete=models.PROTECT)
    students = models.ManyToManyField("students.Student")
    revision = models.PositiveIntegerField(default=1)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(auto_now=True)


# Snapshot an approved roster for a time-bounded attendance meeting.
class AttendanceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=[("open", "Open"), ("closed", "Closed")], default="open")
    roster_revision = models.PositiveIntegerField()
    student_ids = models.JSONField()
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_attendance_sessions")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="closed_attendance_sessions")
    closed_at = models.DateTimeField(null=True)

    # Enforce a positive session window and declare attendance permissions.
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="attendance_positive_window")]
        permissions = [("manage_attendance", "Can manage course attendance sessions"),
                       ("record_attendance", "Can record course attendance"),
                       ("correct_attendance", "Can correct course attendance"),
                       ("view_attendance", "Can view course attendance")]


# Keep each student's attendance status once per session.
class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name="records")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=[("present", "Present"), ("absent", "Absent")], default="present")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=1000)

    # Prevent more than one attendance record per student in a session.
    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "student"], name="unique_student_class_attendance")]


# Record each submitted attendance event, including duplicate submissions.
class AttendanceEvent(models.Model):
    id = models.UUIDField(primary_key=True)
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    duplicate = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)


# Preserve the before-and-after status for each authorized correction.
class AttendanceCorrection(models.Model):
    record = models.ForeignKey(AttendanceRecord, on_delete=models.PROTECT, related_name="corrections")
    previous_status = models.CharField(max_length=10)
    status = models.CharField(max_length=10)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)


# Retain immutable membership snapshots for each confirmed roster revision.
class CourseRosterApproval(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    student_ids = models.JSONField()
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(auto_now_add=True)

    # Keep one immutable approval snapshot for each offering revision.
    class Meta:
        constraints = [models.UniqueConstraint(fields=["offering", "revision"], name="unique_course_roster_approval")]


# Bind unidentified append-only capture evidence and recovery flags to one meeting.
class PendingCaptureBatch(models.Model):
    """Unidentified evidence bound permanently to one real class meeting."""
    id = models.UUIDField(primary_key=True, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name="pending_capture_batches")
    metadata = models.JSONField()
    recovery_review_required = models.BooleanField(default=False)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        permissions = [("import_pending_captures", "Can preview and import pending biometric captures")]


# Store each opaque probe with its bounded ordinal and boot-relative elapsed time.
class PendingCaptureEvent(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    batch = models.ForeignKey(PendingCaptureBatch, on_delete=models.PROTECT, related_name="captures")
    ordinal = models.PositiveSmallIntegerField()
    boot_uuid = models.UUIDField()
    # Decimal text preserves all uint64 bits on both SQLite and PostgreSQL.
    # Only the bounded parser/service writes this field; it is never a clock date.
    uptime_ms = models.CharField(max_length=20, editable=False)
    captured_at = models.DateTimeField(null=True, editable=False)
    probe = models.BinaryField(max_length=2048, editable=False)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["batch", "ordinal"], name="unique_pending_capture_ordinal"),
            models.CheckConstraint(condition=models.Q(ordinal__gte=0, ordinal__lt=512), name="pending_capture_ordinal_bound"),
        ]


# Preserve an idempotent receipt for each accepted file snapshot and retry.
class PendingBatchImport(models.Model):
    """Durable receipt for an accepted file snapshot, including exact retries."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(PendingCaptureBatch, on_delete=models.PROTECT, related_name="imports")
    file_sha256 = models.CharField(max_length=64)
    event_count = models.PositiveSmallIntegerField()
    new_event_count = models.PositiveSmallIntegerField()
    interrupted_write_pending = models.BooleanField()
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["batch", "file_sha256"], name="unique_pending_batch_file_receipt")]


class ScannerReference(models.Model):
    """Administrative mapping of an enrolled scanner slot; never biometric bytes."""
    scanner_uuid = models.UUIDField()
    reference_id = models.CharField(max_length=100)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    disabled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="disabled_scanner_references")
    disabled_at = models.DateTimeField(null=True)
    replaces = models.ForeignKey("self", null=True, on_delete=models.PROTECT)

    class Meta:
        default_permissions = ()
        permissions = [("manage_biometric_reference", "Can enrol and replace student scanner references")]
        constraints = [models.UniqueConstraint(fields=["scanner_uuid", "reference_id"], condition=models.Q(is_active=True), name="unique_active_scanner_reference")]


class CaptureReview(models.Model):
    """Durable review state separate from immutable captured evidence."""
    capture = models.OneToOneField(PendingCaptureEvent, on_delete=models.PROTECT, related_name="review")
    mode = models.CharField(max_length=10, choices=[("live", "Live"), ("deferred", "Deferred")])
    state = models.CharField(max_length=10, choices=[("flagged", "Flagged"), ("archived", "Archived"), ("resolved", "Resolved")])
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_capture_reviews")
    opened_at = models.DateTimeField(auto_now_add=True)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, null=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="resolved_capture_reviews")
    resolved_at = models.DateTimeField(null=True)
    reason = models.CharField(max_length=1000, blank=True)
    record = models.ForeignKey(AttendanceRecord, on_delete=models.PROTECT, null=True)

    class Meta:
        default_permissions = ()


class MeetingFinalisation(models.Model):
    """Append-only review receipt; captures and the meeting roster remain intact."""
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name="finalisations")
    revision = models.PositiveIntegerField()
    evidence_sha256 = models.CharField(max_length=64)
    review_sha256 = models.CharField(max_length=64)
    records_snapshot = models.JSONField()
    excusals_snapshot = models.JSONField(default=list)
    student_ids = models.JSONField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=1000)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["session", "revision"], name="unique_meeting_finalisation_revision")]


class AttendanceExcusal(models.Model):
    """Formal student/meeting exemption, separate from factual attendance."""
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name="excusals")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    is_excused = models.BooleanField(default=False)
    retrospective = models.BooleanField(default=False)
    eligibility_roster_revision = models.PositiveIntegerField(null=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(auto_now=True)
    reason = models.CharField(max_length=1000)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["session", "student"], name="unique_student_meeting_excusal")]


class AttendanceExcusalAction(models.Model):
    """Append-only grant/revocation receipt, including explicit idempotency key."""
    id = models.UUIDField(primary_key=True, editable=False)
    excusal = models.ForeignKey(AttendanceExcusal, on_delete=models.PROTECT, related_name="actions")
    previous_is_excused = models.BooleanField()
    is_excused = models.BooleanField()
    eligibility_roster_revision = models.PositiveIntegerField(null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()


class AttendancePolicyRevision(models.Model):
    event_id = models.UUIDField(unique=True)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT, related_name="attendance_policies")
    minimum_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()


class ExamExceptionDecision(models.Model):
    event_id = models.UUIDField(unique=True)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    enabled = models.BooleanField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
