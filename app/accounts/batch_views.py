from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from academics.views import run_academic_service
from documents.workflow import visible_documents, can_review
from students.models import Student
from record_imports.models import SourcePerformance
from .models import StudentChangeRequest, HODHandover, SourcePerformanceReview
from .batch_services import temporary_account, offer_handover, accept_handover, request_change, review_change, archive_student, review_performance

class ActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['temporary_password', 'change_request', 'archive'])
    email = serializers.EmailField(required=False)
    kind = serializers.ChoiceField(choices=['contact', 'guardian', 'identity'], required=False)
    values = serializers.JSONField(required=False)
    reason = serializers.CharField(max_length=1000, required=False)

def request_data(row):
    return {'id': row.pk, 'kind': row.kind, 'values': row.values, 'reason': row.reason, 'state': row.state, 'review_reason': row.review_reason, 'reviewed_at': row.reviewed_at}

@method_decorator(never_cache, name='dispatch')
class StudentWorkflowView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def student(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        visible_documents(request.user, student)
        return student

    def get(self, request, student_id):
        student = self.student(request, student_id)
        return Response({'student_id': str(student.pk), 'can_review': can_review(request.user, student), 'phone_number': student.phone_number, 'email': student.user.email if student.user_id else '', 'guardians': list(student.guardians.values('guardian_id', 'full_name', 'phone_number', 'relationship', 'email', 'address')), 'requests': [request_data(r) for r in student.change_requests.order_by('-pk')[:100]], 'source_comparisons': [{'id': s.pk, 'review_status': s.review_status, 'source': s.source, 'comparison_at_import': {k: v for k, v in s.comparison_at_import.items() if k != 'inputs'}, 'reviews': list(s.reviews.values('reason', 'created_at', 'notified_hod', 'notification_state'))} for s in student.source_performances.all()]})

    def post(self, request, student_id):
        student = self.student(request, student_id)
        form = ActionSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        action = data['action']
        if action == 'temporary_password':
            if 'email' not in data:
                raise serializers.ValidationError({'email': 'Email is required.'})
            return Response(run_academic_service(temporary_account, actor=request.user, student=student, email=data['email']))
        if action == 'archive':
            run_academic_service(archive_student, actor=request.user, student=student, reason=data.get('reason', ''))
            return Response({'archived': True})
        row = run_academic_service(request_change, user=request.user, student=student, kind=data.get('kind', ''), values=data.get('values', {}), reason=data.get('reason', ''))
        return Response(request_data(row), status=201)

class ReviewSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000)

@method_decorator(never_cache, name='dispatch')
class StudentRequestReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, request_id):
        row = get_object_or_404(StudentChangeRequest, pk=request_id)
        form = ReviewSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        return Response(request_data(run_academic_service(review_change, user=request.user, row=row, **form.validated_data)))

class HandoverSerializer(serializers.Serializer):
    target_id = serializers.IntegerField(min_value=1, required=False)
    handover_id = serializers.IntegerField(min_value=1, required=False)

@method_decorator(never_cache, name='dispatch')
class HandoverView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response(list(HODHandover.objects.filter(Q(sender=request.user) | Q(recipient=request.user)).values('id', 'sender_id', 'recipient_id', 'state', 'created_at', 'accepted_at')))

    def post(self, request):
        form = HandoverSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        if bool(data.get('target_id')) == bool(data.get('handover_id')):
            raise serializers.ValidationError('Choose offer or acceptance.')
        row = run_academic_service(offer_handover, actor=request.user, target_id=data['target_id']) if 'target_id' in data else run_academic_service(accept_handover, actor=request.user, handover_id=data['handover_id'])
        return Response({'id': row.pk, 'state': row.state, 'recipient_id': row.recipient_id})

class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)

@method_decorator(never_cache, name='dispatch')
class PerformanceReviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, source_id):
        source = get_object_or_404(SourcePerformance, pk=source_id)
        form = ReasonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        row = run_academic_service(review_performance, actor=request.user, source=source, **form.validated_data)
        return Response({'id': row.pk, 'source_id': source.pk, 'reason': row.reason, 'notified_hod': row.notified_hod, 'notification_state': row.notification_state})
