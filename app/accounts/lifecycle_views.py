from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError as ModelValidationError
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.settings import api_settings

from students.models import Student
from academics.views import IsActiveHOD, run_academic_service
from .lifecycle import (change_password, request_password_reset, confirm_password_reset,
                        provision_student_account, link_student_account, reset_frontend_url)
from .serializers import (PasswordChangeSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, StudentAccountCreateSerializer, StudentAccountLinkSerializer,
    CurrentUserSerializer)


class RecoveryRateThrottle(ScopedRateThrottle):
    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = run_academic_service(change_password, user=request.user, **serializer.validated_data)
        update_session_auth_hash(request._request, user)
        return Response({"detail": "Password changed."})


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reset_frontend_url()
        except ModelValidationError:
            error = APIException("Password recovery is not configured.")
            error.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            raise error
        # Never return account existence or a reset token through this endpoint.
        request_password_reset(**serializer.validated_data)
        return Response({"detail": "If an eligible account exists, reset instructions will be sent."})


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryRateThrottle]
    throttle_scope = "password_reset_confirm"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(confirm_password_reset, **serializer.validated_data)
        return Response({"detail": "Password reset. Sign in with the new password."})


class StudentAccountView(APIView):
    permission_classes = [IsActiveHOD]

    def post(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        serializer = StudentAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = run_academic_service(provision_student_account,
            user=request.user, student=student, validated_data=serializer.validated_data)
        return Response(CurrentUserSerializer(account).data, status=status.HTTP_201_CREATED)

    def put(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        serializer = StudentAccountLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = run_academic_service(link_student_account,
            user=request.user, student=student, **serializer.validated_data)
        return Response(CurrentUserSerializer(account).data)
