"""One fictional report through the existing email transport; no database access."""
from decimal import Decimal
from types import SimpleNamespace
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from academics.calculations import calculate_weighted_average
from academics.grading import grade_point_for_score
from academics.email_backend import SMTP_BACKENDS
from academics.sharing_transport import (RejectedSubmission, UncertainSubmission,
                                        submit_email, validate_email_configuration)


def mock_report():
    current = [SimpleNamespace(code=code, score=Decimal(score), credit_units=units,
                              attempt=attempt, is_verified=True)
               for code, score, units, attempt in
               [("EEE301", "75", 3, 2), ("EEE303", "65", 2, 1), ("EEE305", "38", 2, 1)]]
    previous = SimpleNamespace(score=Decimal("30"), credit_units=3, is_verified=True)
    gpa = calculate_weighted_average(current)
    cgpa = calculate_weighted_average([previous, *current])
    lines = ["TEST ONLY - FICTIONAL RESULTS. No real student records were used.", "",
             "Student: Demo Student (MOCK-EMAIL-001)",
             "Session: 2026/2027; semester: harmattan"]
    for row in current:
        lines.append(f"{row.code}: score {row.score}, units {row.credit_units}, "
                     f"grade point {grade_point_for_score(row.score)}, attempt {row.attempt}")
    lines += [f"Semester GPA: {gpa:.2f}", f"Cumulative CGPA: {cgpa:.2f}",
              "CGPA includes an earlier failed EEE301 attempt (score 30, units 3).",
              "", "This message tests email transport only. It is not an official result."]
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Preview a fictional guardian report, or send one test email with --to ADDRESS --send."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--to", dest="recipient", help="One authorized test recipient address.")
        parser.add_argument("--send", action="store_true", help="Submit exactly one fictional email.")

    def handle(self, *args, **options):
        recipient = (options["recipient"] or "").strip()
        if recipient:
            try:
                validate_email(recipient)
            except ValidationError:
                raise CommandError("Provide one valid test recipient email address.") from None
        if options["send"] and not recipient:
            raise CommandError("--to ADDRESS is required with --send.")
        body = mock_report()
        if not options["send"]:
            self.stdout.write(body)
            self.stdout.write("Preview only: no email submitted and no database records accessed.")
            return
        if settings.EMAIL_BACKEND not in (*SMTP_BACKENDS, "django.core.mail.backends.locmem.EmailBackend"):
            raise CommandError("Select the SMTP email backend before testing real receipt.")
        try:
            validate_email_configuration()
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from None
        delivery = SimpleNamespace(pk=uuid.uuid4(), destination=recipient,
                                   subject="[TEST ONLY] Guardian result email", body=body)
        try:
            submit_email(delivery)
        except RejectedSubmission:
            raise CommandError("Email provider rejected the test. Check the sender account, App Password and recipient.") from None
        except UncertainSubmission:
            raise CommandError("Submission outcome is uncertain. Check the inbox and sender account before trying again; no automatic retry was made.") from None
        if settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend":
            self.stdout.write("Stored in the in-memory test backend; no real email sent.")
        else:
            self.stdout.write("SMTP accepted one fictional test email. Check the recipient's Inbox and Spam; receipt is not yet confirmed.")
