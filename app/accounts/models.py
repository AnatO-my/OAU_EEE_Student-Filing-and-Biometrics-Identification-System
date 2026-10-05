import re


from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """Account for staff and students using Django authentication and permissions."""

    pass


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

    def __str__(self):
        return (
            f"{self.staff.username} — " f"{self.level} level ({self.academic_session})"
        )

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


class AdviserMessage(models.Model):
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

    def __str__(self):
        return self.subject



class HODMessage(models.Model):
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

    def __str__(self):
        return self.subject
