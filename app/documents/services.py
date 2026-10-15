import os
import tempfile

from django.core.files.base import File
from django.db import transaction
from django.utils import timezone

from .ocr import OcrResult, OcrUnavailable, run_ocr
from dataclasses import dataclass

from django.conf import settings

from .models import StudentDocument
from .ocr import OcrResult


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
            StudentDocument.objects.filter(
                student=student,
                document_type=document_type,
                superseded_at__isnull=True,
            ).update(superseded_at=timezone.now())

            document = StudentDocument(
                student=student,
                document_type=document_type,
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