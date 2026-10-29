"""Private, versioned student filing and explicit replacement review."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone
from accounts.models import AdviserAssignment
from academics.current_session import current_session_name
from students.models import Student
from .models import StudentDocument

def can_review(user, student):
    if not user.is_authenticated:
        return False
    fresh = get_user_model().objects.filter(pk=user.pk, is_active=True, is_staff=True).first()
    return bool(fresh and (fresh.is_superuser or AdviserAssignment.objects.filter(staff=fresh, academic_session=current_session_name(), level=student.current_level, is_active=True).exists()))

def lock_student_actor(user, student_id):
    snapshot = Student.objects.filter(pk=student_id).values_list("user_id", flat=True).first()
    rows = {row.pk: row for row in get_user_model().objects.select_for_update().filter(pk__in={user.pk, snapshot}).order_by("pk")}
    actor = rows.get(user.pk)
    if actor is None or not actor.is_active:
        raise PermissionDenied("An active account is required.")
    student = Student.objects.select_for_update().get(pk=student_id)
    if student.user_id != snapshot:
        raise ValidationError("The linked account changed. Refresh before reviewing.")
    return actor, student

def visible_documents(user, student):
    own = user.is_authenticated and user.is_active and (student.user_id == user.pk)
    if not own and (not can_review(user, student)):
        raise Http404
    return StudentDocument.objects.filter(student=student)

@transaction.atomic
def review_document(*, user, document, approve, reason):
    user, student = lock_student_actor(user, document.student_id)
    if not can_review(user, student):
        raise PermissionDenied('Only the part adviser or HOD may review replacements.')
    document = StudentDocument.objects.select_for_update().get(pk=document.pk)
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError('Record a review reason.')
    state = 'active' if approve else 'rejected'
    if document.approval_state != 'pending':
        if document.reviewed_by_id == user.pk and document.approval_state == state and (document.review_reason == reason):
            return document
        raise ValidationError('This replacement is no longer pending.')
    if approve:
        current = StudentDocument.objects.filter(student=student, document_type=document.document_type, approval_state='active', superseded_at__isnull=True).first()
        if (current.pk if current else None) != document.replaces_id:
            raise ValidationError('The active version changed; submit a new replacement.')
        if current:
            current.approval_state = 'archived'
            current.superseded_at = timezone.now()
            current.save(update_fields=['approval_state', 'superseded_at'])
    document.approval_state = state
    document.reviewed_by = user
    document.reviewed_at = timezone.now()
    document.review_reason = reason
    document.save(update_fields=['approval_state', 'reviewed_by', 'reviewed_at', 'review_reason'])
    return document
