"""OCR hook.

The upload feature calls the function named by settings.DOCUMENT_OCR_BACKEND,
which must look like:

    def extract_text(path: str) -> OcrResult

When Faheezah's OCR module is ready, write a small adapter with that
signature and point DOCUMENT_OCR_BACKEND at it. Nothing else changes.
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class OcrResult:
    text: str
    # 0-100 if the OCR engine reports one, otherwise None.
    confidence: float | None = None


class OcrUnavailable(Exception):
    """Raised when no working OCR engine is configured or it failed to run."""


def placeholder_extract_text(path: str) -> OcrResult:
    raise OcrUnavailable("OCR engine is not configured yet.")


def run_ocr(path: str) -> OcrResult:
    backend = import_string(settings.DOCUMENT_OCR_BACKEND)
    return backend(path)