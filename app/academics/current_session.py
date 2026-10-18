from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CurrentAcademicSession, AcademicSessionSelection
from .services import require_hod


# Resolve the database selection, falling back to the configured session during bootstrap.
def current_session_state():
    selection = CurrentAcademicSession.objects.select_related("academic_session").filter(pk=1).first()
    if selection and selection.academic_session_id:
        return {"academic_session": selection.academic_session_id,
                "name": selection.academic_session.name, "source": "database"}
    # Bootstrap compatibility only, until the HOD selects a database session.
    return {"academic_session": None, "name": settings.CURRENT_ACADEMIC_SESSION,
            "source": "environment"}


def current_session_name():
    return current_session_state()["name"]


@transaction.atomic
# Change the singleton current-session row and record who made the selection.
def select_current_session(*, user, academic_session, expected_session_id):
    require_hod(user)
    academic_session.full_clean()
    selection = CurrentAcademicSession.objects.select_for_update().get(pk=1)
    if selection.academic_session_id != expected_session_id:
        raise ValidationError("The current session changed. Refresh before selecting another.")
    if selection.academic_session_id == academic_session.pk:
        return selection
    AcademicSessionSelection.objects.create(previous_session_id=selection.academic_session_id,
        academic_session=academic_session, actor=user)
    selection.academic_session = academic_session
    selection.updated_by = user
    selection.save()
    return selection
