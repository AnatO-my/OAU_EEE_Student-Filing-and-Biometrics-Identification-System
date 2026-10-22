"""Exact student identity matching shared by registration and reviewed imports."""

from django.core.exceptions import ValidationError
from django.db.models import Q


def identifier_key(value):
    """Preserve punctuation/zeros while treating letter case and edge space equally."""
    if not isinstance(value, str):
        raise ValidationError("Student identifiers must be supplied as text.")
    value = value.strip()
    if not value or len(value) > 100 or not value.isprintable():
        raise ValidationError("Enter an identifier of 1 to 100 characters without control characters.")
    return value.casefold()


def resolve_student_identifier(identifier_type, identifier_value, queryset=None):
    """Resolve the primary identity or a retained alias inside an optional scope."""
    from .models import Student, StudentIdentifier

    key = identifier_key(identifier_value)
    if identifier_type not in Student.IdentifierType.values:
        raise ValidationError("Choose matriculation or UTME identifier type.")
    students = Student.objects.all() if queryset is None else queryset
    aliases = StudentIdentifier.objects.filter(
        identifier_key=key, identifier_type=identifier_type,
    ).values("student_id")
    return students.filter(
        Q(identifier_key=key, identifier_type=identifier_type) | Q(pk__in=aliases),
    ).first()


def identifier_is_unavailable(value, student_id=None):
    from .models import StudentIdentifier

    entries = StudentIdentifier.objects.filter(identifier_key=identifier_key(value))
    if student_id is not None:
        entries = entries.exclude(student_id=student_id)
    return entries.exists()
