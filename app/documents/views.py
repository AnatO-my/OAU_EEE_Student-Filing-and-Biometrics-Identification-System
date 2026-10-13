from django.shortcuts import render

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from students.models import Student

from .models import StudentDocument
from .serializers import DocumentUploadSerializer, StudentDocumentSerializer


class StudentDocumentView(APIView):
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser]

    def post(self, request, student_id):
        student = get_object_or_404(Student, student_id=student_id)

        form = DocumentUploadSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        uploaded = form.validated_data["file"]

        document = StudentDocument.objects.create(
            student=student,
            document_type=form.validated_data["document_type"],
            file=uploaded,
            original_filename=uploaded.name[:255],
            uploaded_by=request.user,
        )
        return Response(
            StudentDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )
