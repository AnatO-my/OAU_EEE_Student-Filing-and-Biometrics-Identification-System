from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import process_upload
from .models import StudentDocument
from .serializers import DocumentUploadSerializer, StudentDocumentSerializer

from students.permissions import StudentModelPermissions
from students.services import students_visible_to


class StudentDocumentView(APIView):
    permission_classes = [permissions.IsAdminUser, StudentModelPermissions]
    parser_classes = [MultiPartParser]
    queryset =  StudentDocument.objects.none()

    def post(self, request, student_id):
        student = get_object_or_404(
            students_visible_to(request.user, settings.CURRENT_ACADEMIC_SESSION), 
            student_id=student_id)

        form = DocumentUploadSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        document, decision = process_upload(
            student=student,
            uploaded_file=form.validated_data["file"],
            document_type=form.validated_data["document_type"],
            uploaded_by=request.user,
        )
        if document is None:
            return Response(
                {
                    "detail": "Document rejected: please upload a clearer scan.",
                    "reasons": decision.reasons,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
         )
        return Response(
            StudentDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )
