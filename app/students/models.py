import uuid

from django.db import IntegrityError, models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError

from .identity import identifier_key


class StudentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if {"identifier_value", "identifier_type", "identifier_key"}.intersection(kwargs):
            raise ValueError("Change student identifiers through the reviewed identity service.")
        return super().update(**kwargs)

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False, update_fields=None, unique_fields=None):
        if ignore_conflicts or update_conflicts:
            raise ValueError("Student identity conflicts require explicit review, not a bulk upsert.")
        objs = list(objs)
        for student in objs:
            student.identifier_key = identifier_key(student.identifier_value)
            student.identifier_value = student.identifier_value.strip()
        with transaction.atomic(using=self.db):
            result = super().bulk_create(objs, batch_size=batch_size)
            StudentIdentifier.objects.using(self.db).bulk_create([
                StudentIdentifier(student_id=student.pk, identifier_type=student.identifier_type,
                    identifier_value=student.identifier_value, identifier_key=student.identifier_key)
                for student in result
            ], batch_size=batch_size)
            return result


# Store student identity, admission, academic status, and account linkage.
class Student(models.Model):
    objects = StudentQuerySet.as_manager()
    # class for admission mode, this is used to identify how a student was admitted into the school.
    class AdmissionMode(models.TextChoices):
        UTME = "utme", "UTME"
        DIRECT_ENTRY = "direct_entry", "Direct Entry"
        TRANSFER = "transfer", "Transfer"

    # class for academic status, this is used to identify the current status of a student in the school.
    class AcademicStatus(models.TextChoices):
        UNDERGRADUATE = "undergraduate", "Undergraduate"
        GRADUATED = "graduated", "Graduated"
        WITHDRAWN = "withdrawn", "Withdrawn"
        LEFT = "left", "Left department"

    # class for identifier type, this is used to identify a student uniquely; utme number is only used as a backup until matriculation number is generated. Matric number is the primary identifier for a student.
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
    identifier_key = models.CharField(max_length=300, unique=True, editable=False)
    full_name = models.CharField(max_length=200)
    programme = models.CharField(max_length=150, blank=True, default="")
    surname = models.CharField(max_length=100, blank=True, default="")
    # Optional biodata entered explicitly rather than inferred from full_name.
    # It remains write-only in the profile API; login uses a separate account
    # and a password chosen by the student, never their surname.
    phone_number = models.CharField(max_length=30, blank=True, default="")
    admission_year = models.PositiveSmallIntegerField()
    mode_of_admission = models.CharField(
        max_length=20,
        choices=AdmissionMode.choices,
    )
    current_level = models.PositiveSmallIntegerField()
    academic_status = models.CharField(
        max_length=20,
        choices=AcademicStatus.choices,
        default=AcademicStatus.UNDERGRADUATE,
    )
    is_active = models.BooleanField(default=True)

    # Keep student listings deterministic and define the explicit export grant.
    class Meta:
        ordering = ["full_name", "student_id"]
        permissions = [("export_student", "Can export student profiles")]

    # Display the student's name alongside the identifier used for lookup.
    def __str__(self):
        return f"{self.full_name} ({self.identifier_value})"

    def clean(self):
        super().clean()
        from .identity import identifier_is_unavailable
        self.identifier_key = identifier_key(self.identifier_value)
        self.identifier_value = self.identifier_value.strip()
        if identifier_is_unavailable(self.identifier_value, self.pk):
            raise ValidationError({"identifier_value": "This identifier is unavailable. Check the entry or ask the HOD to review it."})

    def save(self, *args, **kwargs):
        self.identifier_key = identifier_key(self.identifier_value)
        self.identifier_value = self.identifier_value.strip()
        fields = kwargs.get("update_fields")
        if fields is not None and {"identifier_value", "identifier_type"}.intersection(fields):
            kwargs["update_fields"] = set(fields) | {"identifier_key"}
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            if fields is not None and not {"identifier_value", "identifier_type"}.intersection(fields) and not self._state.adding:
                stored_identity = Student.objects.using(using).filter(pk=self.pk).values_list("identifier_type", "identifier_value").get()
                if stored_identity[0] != self.identifier_type or identifier_key(stored_identity[1]) != self.identifier_key:
                    raise ValueError("A partial save cannot reserve an identity that it does not persist. Refresh the student record.")
            if self.academic_status in {"graduated", "withdrawn", "left"}:
                self.is_active = False
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_active"}
            super().save(*args, **kwargs)
            if not self.is_active and self.user_id:
                from django.contrib.auth import get_user_model
                get_user_model().objects.filter(pk=self.user_id).update(is_active=False)
            entry, _ = StudentIdentifier.objects.using(using).get_or_create(
                identifier_key=self.identifier_key,
                defaults={"student_id": self.pk, "identifier_type": self.identifier_type,
                          "identifier_value": self.identifier_value},
            )
            if entry.student_id != self.pk:
                raise IntegrityError("Student identifier reservation is already owned.")


class StudentIdentifier(models.Model):
    """One global reservation for each current or historical identifier value."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="identifier_aliases")
    identifier_type = models.CharField(max_length=20, choices=Student.IdentifierType.choices)
    identifier_value = models.CharField(max_length=100)
    identifier_key = models.CharField(max_length=300, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.identifier_key = identifier_key(self.identifier_value)
        self.identifier_value = self.identifier_value.strip()
        return super().save(*args, **kwargs)


class StudentIdentityChange(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="identity_changes")
    previous_type = models.CharField(max_length=20)
    previous_value = models.CharField(max_length=100)
    identifier_type = models.CharField(max_length=20)
    identifier_value = models.CharField(max_length=100)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


# class for guardian information, a student can have multiple guardians, but a guardian can only be associated with one student.
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

    # Identify a guardian by name and relationship in admin listings.
    def __str__(self):
        return f"{self.full_name} ({self.relationship})"
