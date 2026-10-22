"""Private setup issuance and CSRF-protected public first-password confirmation."""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .admin_serializers import StrictInput
from .admin_views import HODAdministrationView, invoke
from .lifecycle_views import RecoveryRateThrottle
from .student_setup import confirm_student_setup, issue_student_setup
from .student_access_email import StudentEmailConfigurationError, send_student_access_email


class StudentSetupIssueInput(StrictInput):
    username = serializers.CharField(max_length=150, required=False, trim_whitespace=False)
    email = serializers.EmailField(allow_blank=True, required=False)


class StudentSetupConfirmInput(StrictInput):
    uid = serializers.CharField(max_length=100, trim_whitespace=False, write_only=True)
    token = serializers.CharField(max_length=200, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(max_length=1024, trim_whitespace=False, write_only=True)


class StudentAccountUpdateInput(StrictInput):
    expected_username = serializers.CharField(max_length=150, trim_whitespace=False)
    expected_email = serializers.CharField(max_length=254, allow_blank=True, trim_whitespace=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    use_student_identifier = serializers.BooleanField(default=False)
    expected_identifier_value = serializers.CharField(max_length=100, trim_whitespace=False, required=False)

    def validate(self, values):
        if values.get("use_student_identifier") and "expected_identifier_value" not in values:
            raise serializers.ValidationError({"expected_identifier_value": "Review the current student identifier before using it as the username."})
        if not values.get("use_student_identifier") and "expected_identifier_value" in values:
            raise serializers.ValidationError({"use_student_identifier": "Explicitly confirm the identifier-based username change."})
        return values


class StudentAccessEmailInput(StrictInput):
    expected_username = serializers.CharField(max_length=150, trim_whitespace=False)
    expected_email = serializers.CharField(max_length=254, allow_blank=True, trim_whitespace=False)
    confirm_reissue = serializers.BooleanField()

    def validate_confirm_reissue(self, value):
        if value is not True:
            raise serializers.ValidationError("Explicitly review and confirm sending this account's access link.")
        return value


class StudentSetupIssueView(HODAdministrationView):
    def post(self, request, student_id):
        serializer = StudentSetupIssueInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(invoke(issue_student_setup, actor=self.hod, student_id=student_id,
            values=serializer.validated_data))


class StudentAccessEmailView(HODAdministrationView):
    def post(self, request, student_id):
        serializer = StudentAccessEmailInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = invoke(send_student_access_email, actor=self.hod, student_id=student_id,
                **serializer.validated_data)
        except StudentEmailConfigurationError as error:
            return Response({"detail": str(error), "code": "student_email_not_configured"}, status=503)
        return Response(result)


@method_decorator(never_cache, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
class StudentSetupConfirmView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryRateThrottle]
    throttle_scope = "student_setup_confirm"

    def post(self, request):
        serializer = StudentSetupConfirmInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = invoke(confirm_student_setup, **serializer.validated_data)
        return Response({"detail": "Password set. Sign in with your username and new password.",
            "username": account.username})
