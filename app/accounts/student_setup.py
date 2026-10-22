"""HOD-issued first-login links; students choose their own password once."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from students.models import Student
from .administration import audit, locked_users, require_fresh_hod


class StudentSetupTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "accounts.student_setup.StudentSetupTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        student = Student.objects.filter(user=user).values("student_id", "is_active").first()
        binding = f"{student['student_id']}:{student['is_active']}" if student else "unlinked"
        return f"{super()._make_hash_value(user, timestamp)}:{user.is_active}:{user.is_staff}:{user.is_superuser}:{binding}"

    def check_token(self, user, token):
        if (user is None or not user.is_active or user.is_staff or user.is_superuser
                or user.has_usable_password() or not Student.objects.filter(user=user, is_active=True).exists()):
            return False
        return super().check_token(user, token)


student_setup_tokens = StudentSetupTokenGenerator()


def setup_account_data(account):
    if account is None:
        return None
    return {"id": account.pk, "username": account.username, "email": account.email,
        "is_active": account.is_active, "setup_pending": not account.has_usable_password()}


def student_account(*, actor, student_id):
    require_fresh_hod(actor)
    try:
        student = Student.objects.select_related("user").get(pk=student_id)
    except Student.DoesNotExist:
        raise Http404 from None
    return setup_account_data(student.user)


@transaction.atomic
def issue_student_setup(*, actor, student_id, values):
    snapshot = Student.objects.filter(pk=student_id).values_list("user_id", flat=True).first()
    actor, accounts = locked_users(actor, *([snapshot] if snapshot is not None else []))
    try:
        student = Student.objects.select_for_update().get(pk=student_id)
    except Student.DoesNotExist:
        raise Http404 from None
    if student.user_id != snapshot:
        raise ValidationError("The student account link changed. Refresh the student before issuing another setup link.")
    if not student.is_active:
        raise ValidationError("Only an active student record can receive a login setup link.")
    values = dict(values)
    if set(values) - {"username", "email"}:
        raise ValidationError("Supply only the student username and optional email.")
    if student.user_id is None:
        requested_username = values.get("username", student.identifier_value)
        using_identifier = "username" not in values or requested_username == student.identifier_value
        account = get_user_model()(username=requested_username, email=values.get("email", ""),
            is_active=True, is_staff=False, is_superuser=False)
        account.set_unusable_password()
        account.full_clean()
        if using_identifier and account.username != student.identifier_value:
            raise ValidationError({"username": "This username requires normalization. Review it explicitly instead of silently changing the student identifier."})
        try:
            with transaction.atomic():
                account.save()
        except IntegrityError:
            raise ValidationError({"username": "An account with this username already exists."}) from None
        student.user = account
        student.save(update_fields=["user"])
        action = "student_setup_issued"
    else:
        if values:
            raise ValidationError("This student already has an account. Reissue its pending setup link without changing username or email.")
        account = accounts.get(student.user_id)
        if (account is None or not account.is_active or account.is_staff or account.is_superuser
                or account.has_usable_password()):
            raise ValidationError("Setup links are only available for active student accounts that have not chosen a password. Use password recovery for an existing login.")
        # A new unusable-password salt revokes every previously issued setup token,
        # including reissues within the same second, without storing a raw token.
        account.set_unusable_password()
        account.save(update_fields=["password"])
        action = "student_setup_reissued"
    audit(actor, account, action, {}, {"student_id": str(student.pk),
        "account_id": account.pk, "username": account.username, "setup_pending": True})
    return {"account": setup_account_data(account), "uid": urlsafe_base64_encode(force_bytes(account.pk)),
        "token": student_setup_tokens.make_token(account), "expires_in": settings.PASSWORD_RESET_TIMEOUT}


@transaction.atomic
def confirm_student_setup(*, uid, token, new_password):
    invalid = "The setup link is invalid or expired. Ask the HOD for a new setup link."
    try:
        pk = urlsafe_base64_decode(uid).decode()
        if not pk.isascii() or not pk.isdecimal() or len(pk) > 20:
            raise ValueError
        account = get_user_model().objects.select_for_update().get(pk=int(pk))
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError, get_user_model().DoesNotExist):
        raise ValidationError(invalid) from None
    student = Student.objects.select_for_update().filter(user=account).first()
    if student is None or not student.is_active or not student_setup_tokens.check_token(account, token):
        raise ValidationError(invalid)
    validate_password(new_password, account)
    account.set_password(new_password)
    account.save(update_fields=["password"])
    audit(account, account, "student_setup_completed", {}, {"student_id": str(student.pk),
        "account_id": account.pk, "username": account.username, "setup_pending": False})
    return account


@transaction.atomic
def update_student_login(*, actor, student_id, expected_username, expected_email,
                         email=None, use_student_identifier=False, expected_identifier_value=None):
    snapshot = Student.objects.filter(pk=student_id).values_list("user_id", flat=True).first()
    actor, accounts = locked_users(actor, *([snapshot] if snapshot is not None else []))
    try:
        student = Student.objects.select_for_update().get(pk=student_id)
    except Student.DoesNotExist:
        raise Http404 from None
    if student.user_id != snapshot:
        raise ValidationError("The student account link changed. Refresh it before updating login details.")
    account = accounts.get(snapshot)
    if (account is None or not student.is_active or not account.is_active
            or account.is_staff or account.is_superuser):
        raise ValidationError("Select an active linked student login account.")
    if account.username != expected_username or account.email != expected_email:
        raise ValidationError("The login details changed. Refresh and review the username and email before trying again.")
    if use_student_identifier and student.identifier_value != expected_identifier_value:
        raise ValidationError("The student identifier changed. Refresh it before changing the login username.")
    if email is None and not use_student_identifier:
        raise ValidationError("Choose an email update or explicitly use the student identifier as the username.")
    before = {"student_id": str(student.pk), "account_id": account.pk,
        "username": account.username, "email": account.email}
    requested_username = student.identifier_value if use_student_identifier else account.username
    changed = []
    if email is not None and account.email != email:
        account.email = email
        changed.append("email")
    if use_student_identifier and account.username != student.identifier_value:
        account.username = student.identifier_value
        changed.append("username")
    if changed and not account.has_usable_password():
        account.set_unusable_password()
        changed.append("password")
    account.full_clean()
    if use_student_identifier and account.username != requested_username:
        raise ValidationError({"username": "This username requires normalization. No login details were changed; review the student identifier explicitly."})
    if not use_student_identifier:
        account.username = before["username"]
    if changed:
        try:
            with transaction.atomic():
                account.save(update_fields=changed)
        except IntegrityError:
            raise ValidationError({"username": "Another account already uses this student identifier. No login details were changed."}) from None
        audit(actor, account, "student_login_updated", before,
            {"student_id": str(student.pk), "account_id": account.pk,
             "username": account.username, "email": account.email})
    return setup_account_data(account)
