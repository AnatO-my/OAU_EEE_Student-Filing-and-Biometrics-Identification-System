from django.conf import settings
from rest_framework import serializers

from .models import StudentDocument

PDF_MAGIC = b"%PDF-"


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    document_type = serializers.ChoiceField(
        choices=StudentDocument.DocumentType.choices,
        default=StudentDocument.DocumentType.RESULT,
    )

    def validate_file(self, value):
        if value.size == 0:
            raise serializers.ValidationError("The file is empty.")
        if value.size > settings.DOCUMENT_MAX_UPLOAD_BYTES:
            limit_mb = settings.DOCUMENT_MAX_UPLOAD_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f"The file is larger than {limit_mb} MB.")
        if not value.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are accepted.")
        header = value.read(len(PDF_MAGIC))
        value.seek(0)
        if header != PDF_MAGIC:
            raise serializers.ValidationError("The file is not a valid PDF.")
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
        ]
        read_only_fields = fields