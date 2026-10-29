import re


from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .validators import DepartmentUsernameValidator


# Extend Django's user record for accounts used by staff and students.
class User(AbstractUser):
    """Account for staff and students using Django authentication and permissions."""

    must_change_password = models.BooleanField(default=False)
    username_validator = DepartmentUsernameValidator()
    username = models.CharField(
        _("username"), max_length=150, unique=True,
        help_text=_("Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."),
        validators=[username_validator],
        error_messages={"unique": _("A user with that username already exists.")},
    )


# Assign a staff member to an academic level and session for advising.
class AdviserAssignment(models.Model):
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="adviser_assignments",
        limit_choices_to={"is_staff": True},
    )
    academic_session = models.CharField(max_length=9)
    level = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "academic_session", "level"],
                name="unique_adviser_staff_session_level",
            ),
        ]

    # Show the assignment's owner, level, and session in admin and logs.
    def __str__(self):
        return (
            f"{self.staff.username} — " f"{self.level} level ({self.academic_session})"
        )

    # Validate the session range, staff role, and positive academic level.
    def clean(self):
        super().clean()
        errors = {}

        if not re.fullmatch(r"[0-9]{4}/[0-9]{4}", self.academic_session):
            errors["academic_session"] = "Use YYYY/YYYY, for example 2026/2027."
        else:
            start, end = map(int, self.academic_session.split("/"))
            if end != start + 1:
                errors["academic_session"] = (
                    "The second year must immediately follow the first."
                )

        if self.staff_id and not self.staff.is_staff:
            errors["staff"] = "Select a staff account."

        if self.level == 0:
            errors["level"] = "Level must be greater than zero."

        if errors:
            raise ValidationError(errors)


# Store an adviser's message together with the recipients selected at send time.
class AdviserMessage(models.Model):
    # Distinguish a single-recipient message from a level-wide announcement.
    class Audience(models.TextChoices):
        INDIVIDUAL = "individual", "Individual student"
        LEVEL = "level", "Assigned level"

    assignment = models.ForeignKey(
        AdviserAssignment,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    recipients = models.ManyToManyField(
        "students.Student",
        related_name="adviser_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        permissions = [
            ("send_adviser_message", "Can send adviser messages"),
        ]

    # Display the message subject in admin and related-object listings.
    def __str__(self):
        return self.subject



# Store HOD announcements and the student or adviser recipients selected at send time.
class HODMessage(models.Model):
    # Identify whether the HOD message targets an adviser, student, or level.
    class Audience(models.TextChoices):
        ADVISER = "adviser", "Assigned adviser"
        INDIVIDUAL = "individual", "Individual student"
        LEVEL = "level", "Student level"

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="sent_hod_messages")
    audience = models.CharField(max_length=20, choices=Audience.choices)
    academic_session = models.CharField(max_length=9)
    level = models.PositiveSmallIntegerField(null=True, blank=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    recipients = models.ManyToManyField("students.Student", related_name="hod_messages", blank=True)
    adviser_recipients = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                               related_name="received_hod_messages", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    # Display the message subject in admin and related-object listings.
    def __str__(self):
        return self.subject


class AccountAdministrationAudit(models.Model):
    """Credential-free audit of HOD staff, assignment and ownership changes."""
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="account_administration_actions")
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="account_administration_history")
    action = models.CharField(max_length=30)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        default_permissions = ()


class HODHandover(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='offered_handovers')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='incoming_handovers')
    state = models.CharField(max_length=12, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()

class StudentChangeRequest(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.PROTECT, related_name='change_requests')
    kind = models.CharField(max_length=15)
    values = models.JSONField()
    baseline = models.JSONField(default=dict)
    reason = models.CharField(max_length=1000)
    state = models.CharField(max_length=12, default='pending')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='student_requests')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='student_reviews')
    reviewed_at = models.DateTimeField(null=True)
    review_reason = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()

class SourcePerformanceReview(models.Model):
    source = models.ForeignKey('record_imports.SourcePerformance', on_delete=models.PROTECT, related_name='reviews')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    notified_hod = models.BooleanField(default=False)
    notification_state = models.CharField(max_length=12, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
