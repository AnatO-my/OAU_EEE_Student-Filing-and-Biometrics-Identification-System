from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from students.models import Student
from .models import ResultShareDelivery
from .sharing import build_preview
from .sharing_transport import (RejectedSubmission, UncertainSubmission,
    validate_transport, submit_email, submit_whatsapp)


def process_next():
    # Persist a claim before network I/O. Never automatically reclaim processing
    # rows after a worker crash: the provider may already have accepted them.
    with transaction.atomic():
        candidate = ResultShareDelivery.objects.filter(status="queued").order_by("pk").first()
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
        current, _ = build_preview([student], batch.academic_session, batch.semester, batch.channels)
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
