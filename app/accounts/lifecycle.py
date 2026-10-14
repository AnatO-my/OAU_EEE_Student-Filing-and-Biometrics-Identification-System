import logging

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from students.models import Student
from academics.services import require_hod
from .serializers import LoginSerializer


def reset_frontend_url():
    url = getattr(settings, "PASSWORD_RESET_FRONTEND_URL", "")
    parsed = urlsplit(url)
    if (not parsed.netloc or parsed.scheme not in ("http", "https")
            or parsed.username or parsed.password or parsed.fragment
            or (not settings.DEBUG and parsed.scheme != "https")):
        raise ValidationError("Configure the password-reset frontend URL before enabling recovery.")
    return parsed


def request_password_reset(*, email):
    parsed = reset_frontend_url()
    User = get_user_model()
    for user in User.objects.filter(email__iexact=email, is_active=True):
        if not user.has_usable_password() or not LoginSerializer()._may_sign_in(user):
            continue
        query = parse_qsl(parsed.query) + [
            ("uid", urlsafe_base64_encode(force_bytes(user.pk))),
            ("token", default_token_generator.make_token(user)),
        ]
        link = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
        sent = send_mail("Reset your student-records password",
            f"A password reset was requested for {user.username}.\n\nOpen this link to set a new password:\n{link}\n\nIf you did not request this, ignore this email.",
            settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        if not sent:
            logging.getLogger(__name__).warning("Password-reset email could not be delivered.")


@transaction.atomic
def confirm_password_reset(*, uid, token, new_password):
    User = get_user_model()
    try:
        pk = urlsafe_base64_decode(uid).decode()
        user = User.objects.select_for_update().get(pk=pk, is_active=True)
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
        raise ValidationError("The reset link is invalid or expired.")
    if not user.has_usable_password() or not LoginSerializer()._may_sign_in(user) or not default_token_generator.check_token(user, token):
        raise ValidationError("The reset link is invalid or expired.")
    validate_password(new_password, user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


@transaction.atomic
def change_password(*, user, current_password, new_password):
    user = get_user_model().objects.select_for_update().get(pk=user.pk, is_active=True)
    if not user.check_password(current_password):
        raise ValidationError({"current_password": "The current password is incorrect."})
    validate_password(new_password, user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


@transaction.atomic
def provision_student_account(*, user, student, validated_data):
    require_hod(user)
    student = Student.objects.select_for_update().get(pk=student.pk)
    if student.user_id is not None:
        raise ValidationError("This student already has an account.")
    User = get_user_model()
    account = User(username=validated_data["username"], email=validated_data["email"],
                   is_staff=False, is_superuser=False, is_active=True)
    validate_password(validated_data["password"], account)
    account.set_password(validated_data["password"])
    account.full_clean()
    account.save()
    student.user = account
    student.save(update_fields=["user"])
    return account


@transaction.atomic
def link_student_account(*, user, student, account_id):
    require_hod(user)
    student = Student.objects.select_for_update().get(pk=student.pk)
    try:
        account = get_user_model().objects.select_for_update().get(pk=account_id)
    except get_user_model().DoesNotExist:
        raise ValidationError("Select an existing account.")
    if student.user_id is not None:
        raise ValidationError("This student already has an account.")
    if account.is_staff or account.is_superuser or not account.is_active or not account.has_usable_password():
        raise ValidationError("Select an active nonstaff account with a usable password.")
    if Student.objects.filter(user=account).exists():
        raise ValidationError("This account is already linked to another student.")
    student.user = account
    student.save(update_fields=["user"])
    return account
