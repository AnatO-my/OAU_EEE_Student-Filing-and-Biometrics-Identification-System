import os
import tempfile
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.base import File
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from academics.session_context import current_session_name
from students.models import Student
from students.services import students_visible_to

from .models import StudentDocument
from .ocr import OcrResult, OcrUnavailable, run_ocr


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool  # False means reject: the scan is too unclear to keep
    status: str | None
    reasons: list[str]


def assess_quality(result: OcrResult) -> QualityDecision:
    """Decide whether the OCR output shows a readable document."""
    reasons = []
    if len(result.text.strip()) < settings.DOCUMENT_OCR_MIN_CHARACTERS:
        reasons.append("Almost no readable text was found on the document.")
    if (
        result.confidence is not None
        and result.confidence < settings.DOCUMENT_OCR_MIN_CONFIDENCE
    ):
        reasons.append("The scan is too unclear to read reliably.")
    if reasons:
        return QualityDecision(False, None, reasons)
    return QualityDecision(True, StudentDocument.Status.ACCEPTED, [])


def lock_upload_context(*, student, uploaded_by):
    """Lock in the shared User -> Student order and recheck post-OCR access."""
    User = get_user_model()
    try:
        uploader = User.objects.select_for_update().get(pk=uploaded_by.pk)
    except User.DoesNotExist:
        raise PermissionDenied("An active staff account is required.") from None
    own = not uploader.is_staff and Student.objects.filter(pk=student.pk, user=uploader, is_active=True).exists()
    if not (uploader.is_active and (own or (uploader.is_staff and uploader.has_perm("documents.add_studentdocument")))):
        raise PermissionDenied("You do not have permission to upload student documents.")

    try:
        current_student = Student.objects.select_for_update().get(pk=student.pk)
    except Student.DoesNotExist:
        raise Http404 from None
    if not own and not students_visible_to(uploader, current_session_name()).filter(pk=current_student.pk).exists():
        raise Http404
    return current_student, uploader


def process_upload(*, student, uploaded_file, document_type, uploaded_by):
    """Quality-check the file and keep it only if it passes.

    Returns (document, decision). document is None when the scan is rejected.
    """
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, f"upload{extension}")
        with open(path, "wb") as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        try:
            result = run_ocr(path)
            decision = assess_quality(result)
        except OcrUnavailable:
            # Don't block uploads because OCR isn't set up yet.
            result = OcrResult(text="")
            decision = QualityDecision(
                True,
                StudentDocument.Status.NEEDS_REVIEW,
                ["OCR was not available, so this file needs manual review."],
            )

        if not decision.accepted:
            return None, decision

        with transaction.atomic():
            # All uploaders for the student share this lock, including when no
            # prior document exists yet. OCR itself does not hold database locks.
            student, uploaded_by = lock_upload_context(student=student, uploaded_by=uploaded_by)
            previous = StudentDocument.objects.filter(student=student, document_type=document_type,
                approval_state="active", superseded_at__isnull=True).order_by("-uploaded_at").first()
            pending = previous is not None and not uploaded_by.is_staff
            if previous and not pending:
                previous.superseded_at = timezone.now()
                previous.approval_state = "archived"
                previous.save(update_fields=["superseded_at", "approval_state"])

            document = StudentDocument(
                student=student,
                document_type=document_type,
                replaces=previous,
                approval_state="pending" if pending else "active",
                original_filename=uploaded_file.name[:255],
                status=decision.status,
                ocr_text=result.text,
                ocr_confidence=result.confidence,
                quality_notes=" ".join(decision.reasons)[:255],
                uploaded_by=uploaded_by,
            )
            with open(path, "rb") as stored:
                document.file.save(uploaded_file.name, File(stored), save=False)
            document.save()
    return document, decision
