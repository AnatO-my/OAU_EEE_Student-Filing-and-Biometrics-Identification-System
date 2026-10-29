"""Small HOD-only administration services with fresh authorization and row locks."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404

from academics.models import AcademicSession
from students.models import Student
from .models import AccountAdministrationAudit, AdviserAssignment


MANAGED_PERMISSIONS = frozenset({
    "teaching.publish_message", "teaching.manage_material", "teaching.manage_timetable", "attendance.manage_biometric_reference", "documents.add_studentdocument", "documents.view_studentdocument",
    "students.view_student", "students.add_student", "students.change_student",
    "students.view_guardian", "students.add_guardian", "students.change_guardian",
    "academics.view_result", "academics.add_result", "academics.change_result", "academics.verify_result",
    "attendance.view_attendance", "attendance.manage_attendance", "attendance.record_attendance",
    "attendance.correct_attendance", "attendance.import_pending_captures", "accounts.send_adviser_message",
})


def require_fresh_hod(user):
    if not user.is_authenticated:
        raise PermissionDenied("An active HOD account is required.")
    try:
        fresh = get_user_model().objects.get(pk=user.pk)
    except get_user_model().DoesNotExist:
        raise PermissionDenied("An active HOD account is required.") from None
    if not fresh.is_active or not fresh.is_staff or not fresh.is_superuser:
        raise PermissionDenied("An active HOD account is required.")
    return fresh


def locked_users(actor, *target_ids):
    rows = {row.pk: row for row in get_user_model().objects.select_for_update().filter(
        pk__in={actor.pk, *target_ids}).order_by("pk")}
    current = rows.get(actor.pk)
    if current is None or not current.is_active or not current.is_staff or not current.is_superuser:
        raise PermissionDenied("Your HOD authorization is no longer active. Refresh your account.")
    return current, rows


def permission_map():
    permissions = Permission.objects.select_related("content_type").filter(
        content_type__app_label__in={code.split(".")[0] for code in MANAGED_PERMISSIONS})
    return {f"{permission.content_type.app_label}.{permission.codename}": permission
        for permission in permissions
        if f"{permission.content_type.app_label}.{permission.codename}" in MANAGED_PERMISSIONS}


def selected_permissions(codes):
    options = permission_map()
    if len(codes) != len(set(codes)) or any(code not in options for code in codes):
        raise ValidationError({"permission_codes": "Choose distinct permissions from the staff permission options."})
    return [options[code] for code in codes]


def eligible_staff(user, *, allow_hod=False):
    if not user.is_staff or (user.is_superuser and not allow_hod) or Student.objects.filter(user=user).exists():
        raise ValidationError("Select an ordinary staff account that is not linked to a student.")


def permission_codes(queryset):
    return sorted(f"{row.content_type.app_label}.{row.codename}" for row in queryset.select_related("content_type"))


def staff_data(user):
    direct = permission_codes(user.user_permissions.all())
    inherited = sorted(user.get_group_permissions())
    return {"id": user.pk, "username": user.username, "first_name": user.first_name,
        "last_name": user.last_name, "email": user.email, "is_active": user.is_active,
        "is_hod": bool(user.is_staff and user.is_superuser),
        "can_transfer": bool(user.is_active and user.is_staff and not user.is_superuser
            and user.has_usable_password() and not Student.objects.filter(user=user).exists()),
        "direct_permissions": direct, "inherited_permissions": inherited,
        "effective_permissions": sorted(user.get_all_permissions()) if user.is_active else [],
        "groups": list(user.groups.order_by("name").values_list("name", flat=True))}


def assignment_data(assignment):
    return {"id": assignment.pk, "staff_id": assignment.staff_id,
        "staff_username": assignment.staff.username, "academic_session": assignment.academic_session,
        "level": assignment.level, "is_active": assignment.is_active}


def audit(actor, target, action, before, after):
    AccountAdministrationAudit.objects.create(actor=actor, target=target, action=action, before=before, after=after)


def replace_managed_permissions(user, codes):
    selected = selected_permissions(codes)
    managed_ids = [permission.pk for permission in permission_map().values()]
    # Existing groups and grants outside this UI's allowlist are preserved.
    user.user_permissions.remove(*managed_ids)
    user.user_permissions.add(*selected)
    for key in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(key, None)


@transaction.atomic
def create_staff(*, actor, values):
    actor, _ = locked_users(actor)
    values = dict(values)
    if set(values) - {"username", "password", "first_name", "last_name", "email", "is_active", "permission_codes"}:
        raise ValidationError("Only the displayed staff fields can be changed here.")
    codes, password = values.pop("permission_codes", []), values.pop("password")
    selected_permissions(codes)
    user = get_user_model()(is_staff=True, is_superuser=False, **values)
    validate_password(password, user)
    user.set_password(password)
    user.full_clean()
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        raise ValidationError({"username": "An account with this username already exists."}) from None
    replace_managed_permissions(user, codes)
    audit(actor, user, "staff_created", {}, staff_data(user))
    return user


@transaction.atomic
def update_staff(*, actor, staff_id, values):
    actor, users = locked_users(actor, staff_id)
    target = users.get(staff_id)
    if target is None or not target.is_staff:
        raise Http404
    if target.pk == actor.pk or target.is_superuser:
        raise ValidationError("HOD accounts cannot be edited here. Use ownership transfer to change the HOD.")
    eligible_staff(target)
    before = staff_data(target)
    values = dict(values)
    if set(values) - {"first_name", "last_name", "email", "is_active", "permission_codes"}:
        raise ValidationError("Only staff names, email, active status and managed permissions can be changed here.")
    codes = values.pop("permission_codes", None)
    if codes is not None:
        selected_permissions(codes)
    for field, value in values.items():
        setattr(target, field, value)
    target.full_clean()
    if values:
        target.save(update_fields=list(values))
    if codes is not None:
        replace_managed_permissions(target, codes)
    audit(actor, target, "staff_updated", before, staff_data(target))
    return target


@transaction.atomic
def save_assignment(*, actor, values, assignment_id=None):
    if set(values) - {"staff_id", "academic_session", "level", "is_active"}:
        raise ValidationError("Only the displayed adviser assignment fields can be changed here.")
    existing = AdviserAssignment.objects.filter(pk=assignment_id).first() if assignment_id else None
    if assignment_id and existing is None:
        raise Http404
    staff_id = values.get("staff_id", existing.staff_id if existing else None)
    actor, users = locked_users(actor, staff_id, *([existing.staff_id] if existing else []))
    staff = users.get(staff_id)
    if staff is None:
        raise ValidationError({"staff_id": "Select an existing staff account."})
    deactivating_existing = existing is not None and staff.pk == existing.staff_id and values.get("is_active") is False
    if not deactivating_existing:
        eligible_staff(staff)
        if not staff.is_active:
            raise ValidationError({"staff_id": "Select an active staff account."})
    if existing:
        assignment = AdviserAssignment.objects.select_for_update().select_related("staff").get(pk=assignment_id)
        # A competing reassignment changed the staff lock set: require a fresh view.
        if assignment.staff_id != existing.staff_id:
            raise ValidationError("This assignment changed concurrently. Refresh assignments before retrying.")
        before = assignment_data(assignment)
    else:
        assignment, before = AdviserAssignment(), {}
    for field, value in values.items():
        setattr(assignment, field, value)
    assignment.staff = staff
    if not AcademicSession.objects.filter(name=assignment.academic_session).exists():
        raise ValidationError({"academic_session": "Select an academic session already configured by the department."})
    assignment.full_clean()
    try:
        with transaction.atomic():
            assignment.save()
    except IntegrityError:
        raise ValidationError("This staff/session/level assignment already exists.") from None
    audit(actor, staff, "adviser_updated" if existing else "adviser_created", before, assignment_data(assignment))
    return assignment


@transaction.atomic
def transfer_hod(*, actor, target_staff_id, expected_target_username, current_password, confirmation):
    locked_users(actor,target_staff_id)
    raise ValidationError("Initiate an ownership handover; the incoming HOD must accept before roles change.")
