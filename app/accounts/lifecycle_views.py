from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError as ModelValidationError
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
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


# Resolve recovery throttling rates from the project's REST framework settings.
class RecoveryRateThrottle(ScopedRateThrottle):
    # Use the rate configured for this view's throttle scope.
    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]


# Change an authenticated user's password and preserve their current session.
class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # Validate the submitted credentials before applying the password change.
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = run_academic_service(change_password, user=request.user, **serializer.validated_data)
        update_session_auth_hash(request._request, user)
        return Response({"detail": "Password changed."})


# Accept password recovery requests without disclosing whether an account exists.
@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryRateThrottle]
    throttle_scope = "password_reset"

    # Validate configuration, queue eligible reset email, and return a uniform response.
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


# Complete password recovery using a valid reset token.
@method_decorator(csrf_protect, name="dispatch")
class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryRateThrottle]
    throttle_scope = "password_reset_confirm"

    # Apply the validated reset and require the user to sign in again.
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(confirm_password_reset, **serializer.validated_data)
        return Response({"detail": "Password reset. Sign in with the new password."})


# Let the active HOD create a student account or link an existing one.
@method_decorator(never_cache, name="dispatch")
class StudentAccountView(APIView):
    permission_classes = [IsActiveHOD]

    def get(self, request, student_id):
        from .student_access_email import student_account_metadata
        return Response(run_academic_service(student_account_metadata,
            actor=request.user, student_id=student_id))

    def patch(self, request, student_id):
        from .administration import require_fresh_hod
        from .student_access_email import student_account_metadata
        from .student_setup import update_student_login
        from .student_setup_views import StudentAccountUpdateInput
        actor = require_fresh_hod(request.user)
        serializer = StudentAccountUpdateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(update_student_login, actor=actor, student_id=student_id,
            **serializer.validated_data)
        return Response(run_academic_service(student_account_metadata, actor=actor, student_id=student_id))

    # Provision a least-privilege account for the requested student profile.
    def post(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        serializer = StudentAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = run_academic_service(provision_student_account,
            user=request.user, student=student, validated_data=serializer.validated_data)
        return Response(CurrentUserSerializer(account).data, status=status.HTTP_201_CREATED)

    # Attach an existing eligible account to the requested student profile.
    def put(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        serializer = StudentAccountLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = run_academic_service(link_student_account,
            user=request.user, student=student, **serializer.validated_data)
        return Response(CurrentUserSerializer(account).data)
