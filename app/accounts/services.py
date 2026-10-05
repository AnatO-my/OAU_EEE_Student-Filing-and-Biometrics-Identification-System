from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction

from rest_framework.exceptions import ValidationError

from students.models import Student
from .models import AdviserAssignment
from .models import AdviserMessage

def get_message_assignment(*, user, assignment_id):
    if (
        not user.is_authenticated
        or not user.is_active
        or not user.is_staff
    ):
        raise PermissionDenied("An active staff account is required.")

    if not user.has_perm("accounts.send_adviser_message"):
        raise PermissionDenied("You do not have permission to send messages.")

    academic_session = settings.CURRENT_ACADEMIC_SESSION
    if not academic_session:
        raise PermissionDenied("The current academic session is not configured.")

    assignment = AdviserAssignment.objects.select_for_update().filter(
        pk=assignment_id,
        staff=user,
        academic_session=academic_session,
        is_active=True,
    ).first()

    if assignment is None:
        raise PermissionDenied(
            "You do not have an active assignment for this message."
        )

    return assignment


@transaction.atomic
def send_adviser_message(*, user, validated_data):
    assignment = get_message_assignment(
        user=user,
        assignment_id=validated_data["assignment_id"],
    )

    audience = validated_data["audience"]
    recipient_id = validated_data.get("recipient_id")

    eligible = Student.objects.select_for_update().filter(
        current_level=assignment.level,
        is_active=True,
    )

    if audience == AdviserMessage.Audience.INDIVIDUAL:
        if recipient_id is None:
            raise ValidationError({
                "recipient_id": "Select a student."
            })

        eligible = eligible.filter(pk=recipient_id)

    elif audience == AdviserMessage.Audience.LEVEL:
        if recipient_id is not None:
            raise ValidationError({
                "recipient_id": "Omit this field for level announcements."
            })

    else:
        raise ValidationError({"audience": "Invalid audience."})

    recipients = list(eligible)

    if not recipients:
        raise ValidationError({
            "recipients": "No eligible students match this request."
        })

    message = AdviserMessage(
        assignment=assignment,
        audience=audience,
        subject=validated_data["subject"],
        body=validated_data["body"],
    )
    message.full_clean()
    message.save()
    message.recipients.set(recipients)

    return message