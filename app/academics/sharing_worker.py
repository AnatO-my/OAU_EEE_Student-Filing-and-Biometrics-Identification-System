from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from students.models import Student
from .models import ResultShareDelivery
from .sharing import build_preview
from .sharing_pdf import uses_pdf
from .sharing_transport import (RejectedSubmission, UncertainSubmission,
    validate_transport, submit_email, submit_whatsapp)


# Claim and process one queued delivery, persisting uncertain outcomes to prevent retries.
def process_next(*, channel=None):
    # Persist a claim before network I/O. Never automatically reclaim processing
    # rows after a worker crash: the provider may already have accepted them.
    with transaction.atomic():
        candidates = ResultShareDelivery.objects.filter(status="queued")
        if channel is not None:
            if channel not in ("email", "whatsapp"):
                raise ValueError("Unknown result-sharing channel.")
            candidates = candidates.filter(channel=channel)
        candidate = candidates.order_by("pk").first()
        if candidate is None:
            return None
        claimed = ResultShareDelivery.objects.filter(pk=candidate.pk, status="queued").update(
            status="processing", attempts=F("attempts") + 1, updated_at=timezone.now())
        if not claimed:
            return False
    with transaction.atomic():
        student = Student.objects.select_for_update().get(pk=candidate.student_id)
        delivery = ResultShareDelivery.objects.select_for_update().select_related("batch").get(pk=candidate.pk)
        if delivery.status != "processing":
            return False
        batch = delivery.batch
        current, _ = build_preview([student], batch.academic_session, batch.semester, batch.channels,
            include_pdf=uses_pdf(batch.preview), is_revised=batch.is_revised)
        original = next(row for row in batch.preview if row["student_id"] == str(student.pk))
        if current[0] != original:
            delivery.status, delivery.diagnostic_code = "cancelled", "reviewed_data_changed"
        else:
            try:
                validate_transport(delivery.channel)
                delivery.provider_id = (submit_email(delivery) if delivery.channel == "email"
                                        else submit_whatsapp(delivery))
                delivery.status, delivery.diagnostic_code = "accepted", ""
            except ValidationError:
                delivery.status, delivery.diagnostic_code = "failed", "provider_not_configured"
            except RejectedSubmission:
                delivery.status, delivery.diagnostic_code = "failed", "provider_rejected"
            except UncertainSubmission:
                delivery.status, delivery.diagnostic_code = "unknown", "submission_uncertain"
        delivery.save(update_fields=["status", "diagnostic_code", "provider_id", "updated_at"])
    return True
