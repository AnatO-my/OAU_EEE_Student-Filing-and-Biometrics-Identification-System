from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def grade_point_for(score):
    """Convert a score (0-100) to a grade point on a 5-point scale."""
    score = Decimal(score)
    if score >= 70: return Decimal("5.00")   # A
    if score >= 60: return Decimal("4.00")   # B
    if score >= 50: return Decimal("3.00")   # C
    if score >= 45: return Decimal("2.00")   # D
    if score >= 40: return Decimal("1.00")   # E
    return Decimal("0.00")                   # F


PASS_MARK = Decimal("40")


class Semester(models.TextChoices):
    """The two semesters of a session."""
    HARMATTAN = "HARMATTAN", "Harmattan"
    RAIN = "RAIN", "Rain"


# ---------------- TABLE 1: Students ----------------
class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        TERMINATED = "TERMINATED", "Terminated"

    LEVELS = [(l, str(l)) for l in (100, 200, 300, 400, 500)]

    jamb_reg_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    matric_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    level = models.PositiveSmallIntegerField(choices=LEVELS)
    cgpa = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00")) # Note: kept your existing fields
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    surname = models.CharField(max_length=100, blank=True, default="")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="student_profile",
    )

    must_change_password = models.BooleanField(default=True)

    @property
    def primary_id(self):
        """Returns matric number if available, otherwise falls back to JAMB reg number."""
        return self.matric_number if self.matric_number else self.jamb_reg_number

    def save(self, *args, **kwargs):
        """Instantly shifts login username to matric_number once it is provided."""
        if self.matric_number and self.user:
            self.user.username = self.matric_number
            self.user.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.primary_id} {self.name}"


# ---------------- TABLE 2: Courses ----------------
class Course(models.Model):
    code = models.CharField(max_length=15, unique=True)
    title = models.CharField(max_length=200)
    credit_units = models.PositiveSmallIntegerField()
    level = models.PositiveSmallIntegerField(choices=Student.LEVELS, default=100)
    semester = models.CharField(max_length=10, choices=Semester.choices, default=Semester.HARMATTAN)

    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="required_for")

    def __str__(self):
        return f"{self.code} {self.title}"

# ---------------- TABLE 3: Fingerprint Data (Supports Both Thumbs & Multiple Fingers) ----------------
class FingerprintData(models.Model):
    class FingerChoice(models.TextChoices):
        RIGHT_THUMB = "RIGHT_THUMB", "Right Thumb"
        LEFT_THUMB = "LEFT_THUMB", "Left Thumb"
        RIGHT_INDEX = "RIGHT_INDEX", "Right Index"
        LEFT_INDEX = "LEFT_INDEX", "Left Index"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fingerprints")
    finger_position = models.CharField(
        max_length=20, 
        choices=FingerChoice.choices, 
        default=FingerChoice.RIGHT_THUMB
    )
    template_data = models.TextField(help_text="Base64 or hex string of the fingerprint template")
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "finger_position"],
                name="unique_finger_position_per_student",
            )
        ]

    def __str__(self):
        return f"{self.get_finger_position_display()} for {self.student.primary_id}"


# ---------------- TABLE 4: Attendance (Per Course, Multiple Times a Day) ----------------
class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendances")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField(auto_now_add=True)
    time_in = models.TimeField(auto_now_add=True)
    verification_method = models.CharField(max_length=50, default="Fingerprint")
    is_present = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "date"],
                name="one_attendance_per_student_per_course_per_day",
            )
        ]

    def __str__(self):
        status_str = "Present" if self.is_present else "Absent"
        return f"{self.student.primary_id} - {self.course.code} on {self.date} ({status_str})"


# ---------------- TABLE 5: Results ----------------
class Result(models.Model):
    Semester = Semester

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="results")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="results")
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade_point = models.DecimalField(max_digits=3, decimal_places=2)
    session = models.CharField(max_length=9)
    semester = models.CharField(max_length=10, choices=Semester.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "session"],
                name="one_result_per_course_session",
            )
        ]

    def save(self, *args, **kwargs):
        self.grade_point = grade_point_for(self.score)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.primary_id} {self.course.code} {self.session} {self.get_semester_display()}"


# ---------------- TABLE 6: Semester GPA ----------------
class SemesterGPA(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="semester_gpas")
    session = models.CharField(max_length=9)
    semester = models.CharField(max_length=10, choices=Result.Semester.choices)
    total_units = models.PositiveSmallIntegerField()
    gpa = models.DecimalField(max_digits=3, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "session", "semester"],
                name="one_gpa_per_student_per_semester",
            )
        ]

    def __str__(self):
        return f"{self.student.primary_id} {self.session} {self.get_semester_display()}: {self.gpa}"


# ---------------- TABLE 7: Guardians ----------------
class Guardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardians")
    email = models.EmailField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "email"],
                name="one_guardian_email_per_student",
            )
        ]

    def __str__(self):
        return f"{self.email} (guardian of {self.student.primary_id})"


# ---------------- TABLE 8: Files ----------------
class StudentFile(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="files")
    file_type = models.CharField(max_length=50)
    cloud_url = models.URLField(max_length=500)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "file_type", "cloud_url"],
                name="one_file_link_per_student_and_type",
            )
        ]

    def __str__(self):
        return f"{self.file_type} for {self.student.primary_id}"


# ---------------- TABLE 9: Course registrations ----------------
class CourseRegistration(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="registrations")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="registrations")
    session = models.CharField(max_length=9)
    semester = models.CharField(max_length=10, choices=Semester.choices)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "session"],
                name="one_registration_per_course_session",
            )
        ]

    def __str__(self):
        return f"{self.student.primary_id} registered {self.course.code} ({self.session})"


# ---------------- TABLE 10: Academic calendar ----------------
class AcademicCalendar(models.Model):
    current_session = models.CharField(max_length=9)
    current_semester = models.CharField(max_length=10, choices=Semester.choices,
                                        default=Semester.HARMATTAN)
    registration_open = models.BooleanField(default=False)
    min_units = models.PositiveSmallIntegerField(default=15)
    max_units = models.PositiveSmallIntegerField(default=24)
    warning_gpa = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("2.00"))
    watch_gpa = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("2.25"))


    class Meta:
        verbose_name_plural = "academic calendar"


    @classmethod
    def get_solo(cls):
        calendar = cls.objects.first()
        if calendar is None:
            today = date.today()
            start = today.year if today.month >= 9 else today.year - 1
            first_half = today.month >= 9 or today.month <= 2
            calendar = cls.objects.create(
                current_session=f"{start}/{start + 1}",
                current_semester=Semester.HARMATTAN if first_half else Semester.RAIN,
            )
        return calendar

    def __str__(self):
        return f"{self.current_session} {self.get_current_semester_display()} semester"
    