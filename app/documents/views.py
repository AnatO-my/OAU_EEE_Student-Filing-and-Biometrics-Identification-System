from django.http import FileResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions, serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from academics.views import run_academic_service
from students.models import Student
from .services import process_upload
from .models import StudentDocument
from .serializers import DocumentUploadSerializer, StudentDocumentSerializer
from .workflow import visible_documents, review_document

@method_decorator(never_cache, name='dispatch')
class StudentDocumentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        return Response(StudentDocumentSerializer(visible_documents(request.user, student), many=True).data)

    def post(self, request, student_id):
        if not request.user.is_staff and not Student.objects.filter(user=request.user, is_active=True).exists():
            raise PermissionDenied("A linked active student account is required.")
        student = get_object_or_404(Student, pk=student_id)
        visible_documents(request.user, student)
        form = DocumentUploadSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        document, decision = run_academic_service(process_upload, student=student, uploaded_file=form.validated_data['file'], document_type=form.validated_data['document_type'], uploaded_by=request.user)
        if document is None:
            return Response({'detail': 'Document rejected: please upload a clearer scan.', 'reasons': decision.reasons}, status=422)
        return Response(StudentDocumentSerializer(document).data, status=201)

@method_decorator(never_cache, name='dispatch')
class DocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(StudentDocument.objects.select_related('student'), pk=document_id)
        visible_documents(request.user, document.student)
        response = FileResponse(document.file.open('rb'), as_attachment=True, filename=document.original_filename)
        response['X-Content-Type-Options'] = 'nosniff'
        return response

class ReviewSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000)

@method_decorator(never_cache, name='dispatch')
class DocumentReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, document_id):
        document = get_object_or_404(StudentDocument, pk=document_id)
        form = ReviewSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        return Response(StudentDocumentSerializer(run_academic_service(review_document, user=request.user, document=document, **form.validated_data)).data)
