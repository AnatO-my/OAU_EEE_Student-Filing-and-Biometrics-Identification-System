import uuid

from django.db import models
from django.conf import settings


class Student(models.Model):
    #class for admission mode, this is used to identify how a student was admitted into the school.
    class AdmissionMode(models.TextChoices):
        UTME = "utme", "UTME"
        DIRECT_ENTRY = "direct_entry", "Direct Entry"
        TRANSFER = "transfer", "Transfer"

    #class for identifier type, this is used to identify a student uniquely; utme number is only used as a backup until matriculation number is generated. Matric number is the primary identifier for a student.
    class IdentifierType(models.TextChoices):
        MATRICULATION = "matriculation", "Matriculation number"
        UTME = "utme", "UTME number"

    student_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
    )
    identifier_type = models.CharField(
        max_length=20,
        choices=IdentifierType.choices,
    )
    identifier_value = models.CharField(
        max_length=100,
        unique=True,
    )
    full_name = models.CharField(max_length=200)
    surname = models.CharField(max_length=100, blank=True, default="")
    # The student's surname, stored on its own because it doubles as the
    # student's first-login credential and must never be guessed by parsing
    # full_name; the order of tokens in a full name is not reliable. It is
    # filled in when staff create the account or import the departmental
    # list, and a student with an empty surname cannot use surname login
    # until an administrator sets it. It is deliberately not part of the
    # student API responses while it is still an initial credential.
    phone_number = models.CharField(max_length=30, blank=False)
    admission_year = models.PositiveSmallIntegerField()
    mode_of_admission = models.CharField(
        max_length=20,
        choices=AdmissionMode.choices,
    )
    current_level = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name", "student_id"]

    def __str__(self):
        return f"{self.full_name} ({self.identifier_value})"


#class for guardian information, a student can have multiple guardians, but a guardian can only be associated with one student.
class Guardian(models.Model):
    guardian_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="guardians"
    )
    full_name = models.CharField(max_length=200, blank=False)
    phone_number = models.CharField(max_length=30, blank=False)
    relationship = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"
