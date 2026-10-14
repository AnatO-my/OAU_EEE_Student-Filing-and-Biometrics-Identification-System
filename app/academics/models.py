import uuid
import re
from decimal import Decimal

from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings
from django.utils import timezone


def initial_grading_scale_id():
    return GradingScale.objects.get(name="Initial five-point scale").pk


class AcademicSession(models.Model):
    name = models.CharField(
        max_length=9,
        unique=True,
    )

    class Meta:
        ordering = ["name"]

    def clean(self):
        super().clean()

        if not re.fullmatch(r"[0-9]{4}/[0-9]{4}", self.name):
            raise ValidationError({"name": "Use YYYY/YYYY, for example 2026/2027."})

        start_year, end_year = map(int, self.name.split("/"))

        if end_year != start_year + 1:
            raise ValidationError(
                {"name": "The second year must immediately follow the first."}
            )

    def __str__(self):
        return self.name


class Course(models.Model):
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.title}"


class CourseOffering(models.Model):
    grading_scale = models.ForeignKey(
        "GradingScale", on_delete=models.PROTECT,
        default=initial_grading_scale_id, related_name="offerings",
    )

    class Semester(models.TextChoices):
        HARMATTAN = "harmattan", "Harmattan"
        RAIN = "rain", "Rain"

    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="offerings",
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.PROTECT,
        related_name="course_offerings",
    )
    semester = models.CharField(
        max_length=10,
        choices=Semester.choices,
    )
    level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    credit_units = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "academic_session", "semester"],
                name="unique_course_session_semester",
            ),
        ]

    def __str__(self):
        return (
            f"{self.course.code} — "
            f"{self.academic_session.name} "
            f"({self.get_semester_display()})"
        )


class Result(models.Model):
    grading_scale = models.ForeignKey(
        "GradingScale", on_delete=models.PROTECT,
        default=initial_grading_scale_id, related_name="results",
        editable=False,
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="results",
    )
    offering = models.ForeignKey(
        CourseOffering,
        on_delete=models.PROTECT,
        related_name="results",
    )
    attempt_number = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("100")),
        ],
    )
    credit_units = models.PositiveSmallIntegerField(
        editable=False,
        validators=[MinValueValidator(1)],
    )
    is_verified = models.BooleanField(default=False)

    class Meta:
        permissions = [("verify_result", "Can verify academic results")]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "offering", "attempt_number"],
                name="unique_student_offering_attempt",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student.identifier_value} — "
            f"{self.offering.course.code} "
            f"(attempt {self.attempt_number})"
        )


class GradingScale(models.Model):
    name = models.CharField(max_length=100, unique=True)
    bands = models.JSONField()
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["pk"]

    def clean(self):
        super().clean()
        from .grading import validate_bands
        validate_bands(self.bands)

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            if old.is_published and (
                old.name != self.name or old.bands != self.bands
                or old.is_published != self.is_published
            ):
                raise ValidationError("Published grading versions cannot be changed.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_published:
            raise ValidationError("Published grading versions cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.name



class CourseRequirement(models.Model):
    class Resolution(models.TextChoices):
        RESULT = "result", "Recorded result required"
        EXEMPTION = "exemption", "Reviewed exemption"
        TRANSFER = "transfer", "Reviewed transfer credit"

    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="course_requirements")
    offering = models.ForeignKey(CourseOffering, on_delete=models.PROTECT)
    resolution = models.CharField(max_length=20, choices=Resolution.choices, default=Resolution.RESULT)
    reason = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "offering"], name="unique_student_course_requirement")]

    def clean(self):
        super().clean()
        if self.resolution != self.Resolution.RESULT and not self.reason.strip():
            raise ValidationError({"reason": "Explain the reviewed transfer or exemption."})


class GraduationReview(models.Model):
    student = models.OneToOneField("students.Student", on_delete=models.PROTECT, related_name="graduation_review")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField()
    history_digest = models.CharField(max_length=64)
    cgpa_snapshot = models.CharField(max_length=100)


class GuardianSharingPreference(models.Model):
    guardian = models.OneToOneField("students.Guardian", on_delete=models.PROTECT,
                                   related_name="result_sharing_preference")
    email_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    evidence = models.TextField()
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class ResultShareBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT)
    semester = models.CharField(max_length=10, choices=CourseOffering.Semester.choices)
    student_ids = models.JSONField()
    channels = models.JSONField()
    preview = models.JSONField()
    history_digest = models.CharField(max_length=64)
    queued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ResultShareDelivery(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Ready for review"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Submission in progress"
        ACCEPTED = "accepted", "Accepted by provider"
        FAILED = "failed", "Rejected or not submitted"
        UNKNOWN = "unknown", "Submission outcome uncertain"
        SKIPPED = "skipped", "Skipped"
        CANCELLED = "cancelled", "Contact or permission changed"

    batch = models.ForeignKey(ResultShareBatch, on_delete=models.PROTECT, related_name="deliveries")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    guardian = models.ForeignKey("students.Guardian", on_delete=models.PROTECT, null=True)
    channel = models.CharField(max_length=10, choices=[("email", "Email"), ("whatsapp", "WhatsApp")])
    destination = models.CharField(max_length=254, blank=True)
    part_number = models.PositiveSmallIntegerField(default=1)
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    diagnostic_code = models.CharField(max_length=50, blank=True)
    provider_id = models.CharField(max_length=200, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "guardian", "channel", "part_number"],
                                               name="unique_guardian_channel_part_per_share_batch")]
