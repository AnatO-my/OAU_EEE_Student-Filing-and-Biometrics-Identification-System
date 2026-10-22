"""Explicit student setup/reset email submission, independent of result workers."""
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from academics.email_backend import SMTP_BACKENDS
from academics.sharing_transport import validate_email_configuration
from students.models import Student
from .administration import audit, locked_users, require_fresh_hod
from .student_setup import setup_account_data, student_setup_tokens


class StudentEmailConfigurationError(Exception):
    pass


def access_email_configuration():
    origin = getattr(settings, "STUDENT_ACCOUNT_FRONTEND_ORIGIN", "").strip()
    try:
        parsed = urlsplit(origin)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (not parsed.netloc or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or "*" in origin or "\\" in origin or any(char.isspace() for char in origin)
                or (parsed.scheme != "https" and not (parsed.scheme == "http" and settings.DEBUG and loopback))):
            raise ValueError
        parsed.port
    except ValueError:
        raise StudentEmailConfigurationError("Configure a valid student-account frontend origin in the backend terminal.") from None
    if settings.EMAIL_BACKEND not in SMTP_BACKENDS:
        raise StudentEmailConfigurationError("Configure a real SMTP email backend before sending student access links.")
    try:
        validate_email_configuration()
        if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
            raise ValidationError("Choose one SMTP TLS mode.")
        if not settings.EMAIL_USE_TLS and not settings.EMAIL_USE_SSL:
            raise ValidationError("Use encrypted SMTP transport.")
        if not 1 <= settings.EMAIL_PORT <= 65535:
            raise ValidationError("Use a valid SMTP port.")
        if bool(settings.EMAIL_HOST_USER) != bool(settings.EMAIL_HOST_PASSWORD):
            raise ValidationError("Configure both SMTP authentication values.")
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise StudentEmailConfigurationError("Complete the SMTP sender, authentication and encrypted transport settings in the backend terminal.") from None
    return origin.rstrip("/")


def email_configuration_status():
    try:
        access_email_configuration()
    except StudentEmailConfigurationError as error:
        return {"email_delivery_available": False, "email_delivery_detail": str(error)}
    return {"email_delivery_available": True,
        "email_delivery_detail": "SMTP submission is configured. Acceptance does not confirm delivery to the inbox."}


def student_account_metadata(*, actor, student_id):
    require_fresh_hod(actor)
    try:
        student = Student.objects.select_related("user").get(pk=student_id)
    except Student.DoesNotExist:
        raise Http404 from None
    return {"account": setup_account_data(student.user), "preferred_username": student.identifier_value,
        **email_configuration_status()}


@transaction.atomic
def prepare_access_email(*, actor, student_id, expected_username, expected_email, confirm_reissue, origin):
    snapshot = Student.objects.filter(pk=student_id).values_list("user_id", flat=True).first()
    actor, accounts = locked_users(actor, *([snapshot] if snapshot is not None else []))
    try:
        student = Student.objects.select_for_update().get(pk=student_id)
    except Student.DoesNotExist:
        raise Http404 from None
    if student.user_id != snapshot:
        raise ValidationError("The student account link changed. Refresh it before emailing access.")
    account = accounts.get(snapshot)
    if (not confirm_reissue or account is None or not student.is_active or not account.is_active
            or account.is_staff or account.is_superuser):
        raise ValidationError("Explicitly confirm an active linked student account before emailing access.")
    if account.username != expected_username or account.email != expected_email:
        raise ValidationError("The login username or saved email changed. Refresh and review the recipient before sending.")
    validate_email(account.email)
    if account.has_usable_password():
        kind, route = "reset", "/reset-password"
        token = default_token_generator.make_token(account)
    else:
        kind, route = "setup", "/setup-student"
        account.set_unusable_password()
        account.save(update_fields=["password"])
        token = student_setup_tokens.make_token(account)
    uid = urlsafe_base64_encode(force_bytes(account.pk))
    link = origin + route + "#" + urlencode({"uid": uid, "token": token})
    local_note = ("\nOpen this link on the laptop running the department portal; it cannot open the app from another device.\n"
        if urlsplit(origin).hostname in {"127.0.0.1", "localhost", "::1"} else "")
    audit(actor, account, "student_access_email_issued", {}, {"student_id": str(student.pk),
        "account_id": account.pk, "username": account.username, "recipient": account.email,
        "kind": kind, "submission_requested": True})
    return {"account": setup_account_data(account), "kind": kind, "recipient": account.email,
        "body": f"Your departmental student login username is: {account.username}\n\n"
            f"{'Choose your first password' if kind == 'setup' else 'Choose a new password if you need to recover access'} using this private link:\n{link}\n\n"
            f"The link expires after {settings.PASSWORD_RESET_TIMEOUT // 60} minutes and can be used once.\n"
            "Do not forward it or share your password. If you did not expect this message, contact the department."
            + local_note}


def send_student_access_email(*, actor, student_id, expected_username, expected_email, confirm_reissue):
    # Validate before rotating a pending token. The atomic preparation commits
    # and releases user/student locks before any SMTP connection is opened.
    origin = access_email_configuration()
    prepared = prepare_access_email(actor=actor, student_id=student_id, expected_username=expected_username,
        expected_email=expected_email, confirm_reissue=confirm_reissue, origin=origin)
    try:
        count = EmailMessage("Your departmental student account access", prepared.pop("body"),
            settings.DEFAULT_FROM_EMAIL, [prepared["recipient"]]).send(fail_silently=False)
        status = "accepted" if count == 1 else "unknown"
    except Exception:
        # A network/provider error can occur after SMTP acceptance. Never emit
        # raw exceptions or automatically resend an uncertain submission.
        status = "unknown"
    return {**prepared, "delivery_status": status,
        "detail": ("SMTP accepted the access email. Ask the student to check their inbox and spam folder; inbox delivery is not confirmed."
            if status == "accepted" else "Email acceptance could not be confirmed. Check the student's inbox before explicitly sending another link; no automatic retry was performed.")}
