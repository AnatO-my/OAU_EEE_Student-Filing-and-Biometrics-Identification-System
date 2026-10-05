from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .models import AdviserAssignment, User, AdviserMessage
from students.models import Student


class AdviserAssignmentValidationTests(SimpleTestCase):
    def assignment(self, **changes):
        values = {
            "academic_session": "2026/2027",
            "level": 300,
        }
        values.update(changes)
        return AdviserAssignment(**values)

    def test_valid_session_is_accepted(self):
        self.assignment().clean()

    def test_invalid_session_format_is_rejected(self):
        with self.assertRaises(ValidationError) as error:
            self.assignment(academic_session="2026-2027").clean()

        self.assertIn("academic_session", error.exception.message_dict)

    def test_nonconsecutive_years_are_rejected(self):
        with self.assertRaises(ValidationError) as error:
            self.assignment(academic_session="2026/2028").clean()

        self.assertIn("academic_session", error.exception.message_dict)

    def test_zero_level_is_rejected(self):
        with self.assertRaises(ValidationError) as error:
            self.assignment(level=0).clean()

        self.assertIn("level", error.exception.message_dict)

    def test_nonstaff_account_is_rejected(self):
        user = User(pk=1, username="example-student", is_staff=False)

        with self.assertRaises(ValidationError) as error:
            self.assignment(staff=user).clean()

        self.assertIn("staff", error.exception.message_dict)


class AdviserMessageTests(TestCase):
    def test_level_change_preserves_existing_message(self):
        adviser = User.objects.create_user(
            username="example-adviser",
            is_staff=True,
        )
        assignment = AdviserAssignment.objects.create(
            staff=adviser,
            academic_session="2026/2027",
            level=300,
        )
        student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="TEST-001",
            full_name="Example Student",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        message = AdviserMessage.objects.create(
            assignment=assignment,
            audience=AdviserMessage.Audience.LEVEL,
            subject="Advising meeting",
            body="Please attend the scheduled meeting.",
        )
        message.recipients.add(student)

        student.current_level = 400
        student.save(update_fields=["current_level"])

        self.assertTrue(message.recipients.filter(pk=student.pk).exists())
        self.assertTrue(student.adviser_messages.filter(pk=message.pk).exists())
