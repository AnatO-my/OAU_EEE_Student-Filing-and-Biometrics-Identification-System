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