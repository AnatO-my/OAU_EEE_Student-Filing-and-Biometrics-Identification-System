from django.conf import settings
from rest_framework import serializers

from .models import StudentDocument

import os

FILE_SIGNATURES = {
    ".pdf": b"%PDF-",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    document_type = serializers.ChoiceField(
        choices=StudentDocument.DocumentType.choices,
    )

    def validate_file(self, value):
        if value.size == 0:
            raise serializers.ValidationError("The file is empty.")
        if value.size > settings.DOCUMENT_MAX_UPLOAD_BYTES:
            limit_mb = settings.DOCUMENT_MAX_UPLOAD_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f"The file is larger than {limit_mb} MB.")
        extension = os.path.splitext(value.name.lower())[1]
        signature = FILE_SIGNATURES.get(extension)
        if signature is None:
            raise serializers.ValidationError(
                "Only PDF, JPEG and PNG files are accepted."
            )
        header = value.read(len(signature))
        value.seek(0)
        if header != signature:
            raise serializers.ValidationError("The file content does not match its type.")
        return value
class StudentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDocument
        fields = [
            "document_id",
            "student",
            "document_type",
            "original_filename",
            "uploaded_at",
            "status",
            "ocr_confidence",
            "quality_notes",
        ]
        read_only_fields = fields