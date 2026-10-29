"""Reviewed student changes, credential setup, and accepted HOD handover."""
import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from students.models import Student, Guardian
from documents.workflow import can_review, lock_student_actor
from .models import HODHandover, StudentChangeRequest, SourcePerformanceReview
from .administration import require_fresh_hod, eligible_staff, audit

def require_reviewer(user, student):
    if not can_review(user, student):
        raise PermissionDenied('The part adviser or HOD must review this student.')

def safe_email(subject, body, recipients):
    if not recipients:
        raise ValidationError('An email address is required.')
    if settings.EMAIL_BACKEND in {'django.core.mail.backends.console.EmailBackend', 'django.core.mail.backends.filebased.EmailBackend', 'academics.email_backend.SafeConsoleEmailBackend'}:
        raise ValidationError('Configure a real or isolated-memory email backend before sending credentials.')
    if send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False) != 1:
        raise ValidationError('Email delivery was not accepted; no account changes were saved.')

@transaction.atomic
def temporary_account(*, actor, student, email):
    actor, student = lock_student_actor(actor, student.pk)
    require_reviewer(actor, student)
    if not student.is_active:
        raise ValidationError('Archived students cannot receive credentials.')
    validate_email(email)
    if settings.EMAIL_BACKEND not in {'django.core.mail.backends.smtp.EmailBackend', 'academics.email_backend.EmailBackend', 'django.core.mail.backends.locmem.EmailBackend'}:
        raise ValidationError('Configure SMTP or an isolated-memory email backend before issuing temporary passwords.')
    User = get_user_model()
    account = User.objects.select_for_update().filter(pk=student.user_id).first() if student.user_id else None
    if account and (account.is_staff or (not account.must_change_password and account.has_usable_password())):
        raise ValidationError('Use password recovery for an established account.')
    password = secrets.token_urlsafe(18)
    if account is None:
        account = User(username=student.identifier_value, is_staff=False, is_active=True)
    account.email = email
    account.must_change_password = True
    account.is_active = True
    account.set_password(password)
    account.full_clean()
    account.save()
    student.user = account
    student.save(update_fields=['user'])
    try:
        safe_email('Your student account temporary password', f'Username: {account.username}\nTemporary password: {password}\nSign in and change this password before using the system.', [email])
        delivery_status = 'accepted'
    except Exception:
        delivery_status = 'unknown'
    audit(actor, account, 'temporary_password_issued', {}, {'student_id': str(student.pk), 'must_change_password': True, 'delivery_status': delivery_status})
    return {'account_id': account.pk, 'username': account.username, 'must_change_password': True, 'delivery_status': delivery_status}

@transaction.atomic
def offer_handover(*, actor, target_id):
    User = get_user_model()
    rows = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=[actor.pk, target_id]).order_by('pk')}
    actor = require_fresh_hod(rows[actor.pk])
    target = rows.get(target_id)
    if not target or target.pk == actor.pk:
        raise ValidationError('Choose another active staff account.')
    eligible_staff(target)
    if not target.is_active or not target.has_usable_password():
        raise ValidationError('Choose an active staff account with a password.')
    pending = HODHandover.objects.filter(sender=actor, state='pending').first()
    if pending:
        if pending.recipient_id == target.pk:
            return pending
        pending.state = 'cancelled'
        pending.save(update_fields=['state'])
    row = HODHandover.objects.create(sender=actor, recipient=target)
    audit(actor, target, 'hod_transfer_offered', {}, {'handover_id': row.pk})
    return row

@transaction.atomic
def accept_handover(*, actor, handover_id):
    User = get_user_model()
    row = HODHandover.objects.get(pk=handover_id)
    users = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=[row.sender_id, row.recipient_id]).order_by('pk')}
    row = HODHandover.objects.select_for_update().get(pk=row.pk)
    recipient = users[row.recipient_id]
    sender = users[row.sender_id]
    if recipient.pk != actor.pk or not recipient.is_active or (not recipient.is_staff):
        raise PermissionDenied('Only the incoming staff member may accept.')
    if row.state == 'accepted':
        return row
    if row.state != 'pending':
        raise ValidationError('This handover is no longer available.')
    require_fresh_hod(sender)
    eligible_staff(recipient)
    sender.is_superuser = False
    sender.save(update_fields=['is_superuser'])
    recipient.is_superuser = True
    recipient.save(update_fields=['is_superuser'])
    row.state = 'accepted'
    row.accepted_at = timezone.now()
    row.save(update_fields=['state', 'accepted_at'])
    audit(sender, recipient, 'hod_transfer_accepted', {'old_hod': sender.pk}, {'new_hod': recipient.pk, 'handover_id': row.pk})
    return row

def change_baseline(student, kind, values):
    if kind == 'contact':
        return {'phone_number': student.phone_number, 'email': student.user.email if student.user_id else ''}
    if kind == 'guardian':
        gid = values.get('guardian_id')
        guardian = Guardian.objects.filter(pk=gid, student=student).first() if gid else None
        if gid and (not guardian):
            raise ValidationError('Choose your own guardian.')
        return {k: getattr(guardian, k) for k in ('full_name', 'phone_number', 'relationship', 'email', 'address')} if guardian else {}
    return {k: getattr(student, k) for k in ('full_name', 'current_level', 'identifier_type', 'identifier_value', 'programme')}

@transaction.atomic
def request_change(*, user, student, kind, values, reason):
    user, student = lock_student_actor(user, student.pk)
    if student.user_id != user.pk or not user.is_active:
        raise PermissionDenied('Submit corrections for your own record.')
    if kind not in {'contact', 'guardian', 'identity'} or not isinstance(values, dict) or (not reason.strip()):
        raise ValidationError('Choose a correction type and give a reason.')
    allowed = {'contact': {'phone_number', 'email'}, 'guardian': {'guardian_id', 'full_name', 'phone_number', 'relationship', 'email', 'address'}, 'identity': {'full_name', 'current_level', 'identifier_value', 'identifier_type', 'programme'}}[kind]
    if not values or set(values) - allowed:
        raise ValidationError('Unsupported correction fields.')
    if 'email' in values and values['email']:
        validate_email(values['email'])
    return StudentChangeRequest.objects.create(student=student, kind=kind, values=values, baseline=change_baseline(student, kind, values), reason=reason.strip(), created_by=user)

@transaction.atomic
def review_change(*, user, row, approve, reason):
    user, student = lock_student_actor(user, row.student_id)
    require_reviewer(user, student)
    row = StudentChangeRequest.objects.select_for_update().get(pk=row.pk)
    if row.state != 'pending':
        raise ValidationError('This request has already been reviewed.')
    if change_baseline(student, row.kind, row.values) != row.baseline:
        raise ValidationError('The active details changed; request a fresh proposal.')
    if not reason.strip():
        raise ValidationError('Record the review reason.')
    if approve:
        if row.kind == 'identity':
            from students.services import update_student, promote_student_identifier, correct_student_identifier
            values = dict(row.values)
            target_type = values.pop('identifier_type', student.identifier_type)
            if target_type != student.identifier_type and not (student.identifier_type == 'utme' and target_type == 'matriculation'):
                raise ValidationError('Only UTME-to-matriculation promotion may change identifier type.')
            identifier = values.pop('identifier_value', None)
            if identifier and identifier != student.identifier_value:
                if target_type != student.identifier_type:
                    student = promote_student_identifier(user=user, student=student, identifier_value=identifier, expected_identifier_type=student.identifier_type, expected_identifier_value=student.identifier_value)
                else:
                    student = correct_student_identifier(user=user, student=student, identifier_value=identifier, expected_identifier_value=student.identifier_value)
            if values:
                student = update_student(user=user, student=student, validated_data=values)
        elif change_baseline(student, row.kind, row.values) != row.baseline:
            raise ValidationError('The active details changed; request a fresh proposal.')
        values = dict(row.values)
        if row.kind == 'contact':
            if 'phone_number' in values:
                student.phone_number = values['phone_number']
                student.full_clean()
                student.save(update_fields=['phone_number'])
            if 'email' in values:
                if not student.user_id:
                    raise ValidationError('Student has no linked account.')
                account = get_user_model().objects.select_for_update().get(pk=student.user_id)
                account.email = values['email']
                account.full_clean()
                account.save(update_fields=['email'])
        elif row.kind == 'guardian':
            gid = values.pop('guardian_id', None)
            guardian = Guardian.objects.select_for_update().get(pk=gid, student=student) if gid else Guardian(student=student)
            for k, v in values.items():
                setattr(guardian, k, v)
            guardian.full_clean()
            guardian.save()
    row.state = 'approved' if approve else 'rejected'
    row.reviewed_by = user
    row.reviewed_at = timezone.now()
    row.review_reason = reason.strip()
    row.save(update_fields=['state', 'reviewed_by', 'reviewed_at', 'review_reason'])
    return row

@transaction.atomic
def archive_student(*, actor, student, reason):
    actor, student = lock_student_actor(actor, student.pk)
    require_fresh_hod(actor)
    if not reason.strip():
        raise ValidationError('Record an archive reason.')
    student.is_active = False
    student.save(update_fields=['is_active'])
    if student.user_id:
        account = get_user_model().objects.select_for_update().get(pk=student.user_id)
        account.is_active = False
        account.save(update_fields=['is_active'])
        audit(actor, account, 'student_archived', {}, {'student_id': str(student.pk), 'reason': reason.strip()})
    return student

@transaction.atomic
def review_performance(*, actor, source, reason):
    from record_imports.models import SourcePerformance
    source = SourcePerformance.objects.select_for_update().select_related('student').get(pk=source.pk)
    actor, student = lock_student_actor(actor, source.student_id)
    require_reviewer(actor, student)
    if not reason.strip():
        raise ValidationError('Record a discrepancy review reason.')
    row = SourcePerformanceReview.objects.create(source=source, actor=actor, reason=reason.strip())
    source.review_status = 'reviewed'
    source.save(update_fields=['review_status'])
    recipients = list(get_user_model().objects.filter(is_active=True, is_staff=True, is_superuser=True).exclude(email='').values_list('email', flat=True))
    if recipients:
        try:
            count = send_mail('Source GPA discrepancy reviewed', f'A part adviser reviewed source comparison {source.pk}. Sign in to review the retained values and reason.', settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
            row.notification_state = 'accepted' if count == 1 else 'unknown'
        except Exception:
            row.notification_state = 'unknown'
        row.notified_hod = row.notification_state == 'accepted'
        row.save(update_fields=['notified_hod', 'notification_state'])
    return row
