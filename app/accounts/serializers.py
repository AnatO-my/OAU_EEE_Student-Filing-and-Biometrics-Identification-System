from academics.session_context import current_session_name
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from .models import AdviserMessage, HODMessage


# Validate credentials and restrict API sign-in to accounts with an API role.
class LoginSerializer(serializers.Serializer):
    #class for validating the credentials posted by a staff member or a student, the
    #password is write only so it can never be read back out of a serialised
    #representation
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    # Decide whether this account has the staff role or a linked student profile.
    #method that reports whether an account is allowed to sign in to the JSON API, a
    #staff account may always sign in and a student account must be linked to a student
    #profile so an account with no role cannot reach the API at all
    def _may_sign_in(self, user):
        if user.is_staff:
            return True

        try:
            user.student_profile
        except ObjectDoesNotExist:
            return False

        return True

    # Authenticate credentials and return one uniform rejection for ineligible users.
    #method that checks the credentials and rejects anything that is not an account
    #allowed to use the API
    def validate(self, attrs):
        request = self.context.get("request")
        django_request = getattr(request, "_request", None)

        user = authenticate(
            request=django_request,
            username=attrs["username"],
            password=attrs["password"],
        )

        #the same error is raised for an unknown username, a wrong password, an
        #inactive account, and an account that has no API role so the endpoint cannot
        #be used to discover which accounts exist
        if user is None or not user.is_active or not self._may_sign_in(user):
            raise serializers.ValidationError("Invalid username or password.")

        attrs["user"] = user
        return attrs


# Expose the signed-in user's safe identity, role, permissions, and current adviser levels.
class CurrentUserSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    adviser_levels = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    # Return effective permissions only while the account remains active.
    def get_permissions(self, user):
        return sorted(user.get_all_permissions()) if user.is_active else []

    # List distinct active adviser levels for the configured academic session.
    def get_adviser_levels(self, user):
        from django.conf import settings
        if not current_session_name() or not user.is_active or not user.is_staff:
            return []
        return list(user.adviser_assignments.filter(academic_session=current_session_name(),
            is_active=True).order_by("level").values_list("level", flat=True).distinct())

    # Map account flags to the frontend's HOD, staff, or student role.
    def get_role(self, user):
        return "hod" if user.is_staff and user.is_superuser else "staff" if user.is_staff else "student"

    # class that reports the signed in staff member so the frontend can gate its
    # interface, it is only ever read, the frontend never writes through it
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "is_superuser",
            "groups",
            "permissions",
            "adviser_levels",
            "role",
        ]
        read_only_fields = fields


# Check that the chosen adviser-message audience has exactly the required target.
class AdviserMessageSendSerializer(serializers.Serializer):

    assignment_id = serializers.IntegerField(min_value=1)
    audience = serializers.ChoiceField(
        choices=AdviserMessage.Audience.choices,
    )
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField()
    recipient_id = serializers.UUIDField(required=False)

    # Require an individual student ID and reject target IDs for level notices.
    def validate(self, attrs):
        audience = attrs["audience"]
        recipient_id = attrs.get("recipient_id")

        if audience == AdviserMessage.Audience.INDIVIDUAL:
            if recipient_id is None:
                raise serializers.ValidationError(
                    {"recipient_id": "Select a student for an individual message."}
                )

        elif recipient_id is not None:
            raise serializers.ValidationError(
                {
                    "recipient_id": (
                        "Omit this field for a level announcement. "
                        "The backend selects the recipients."
                    )
                }
            )

        return attrs


# Serialize an adviser message visible to one of its student recipients.
class StudentMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = AdviserMessage
        fields = [
            "id",
            "audience",
            "subject",
            "body",
            "sender_name",
            "created_at",
        ]
        read_only_fields = fields

    # Prefer the sender's full name, falling back to their username.
    def get_sender_name(self, obj):
        sender = obj.assignment.staff
        return sender.get_full_name() or sender.username


# Validate audience-specific target fields for messages sent by the HOD.
class HODMessageSendSerializer(serializers.Serializer):
    audience = serializers.ChoiceField(choices=HODMessage.Audience.choices)
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField()
    recipient_id = serializers.UUIDField(required=False)
    adviser_id = serializers.IntegerField(min_value=1, required=False)
    level = serializers.IntegerField(min_value=1, max_value=32767, required=False)

    # Require exactly the field associated with the selected audience.
    def validate(self, attrs):
        target_field = {
            HODMessage.Audience.INDIVIDUAL: "recipient_id",
            HODMessage.Audience.ADVISER: "adviser_id",
            HODMessage.Audience.LEVEL: "level",
        }[attrs["audience"]]
        if target_field not in attrs:
            raise serializers.ValidationError({target_field: "This field is required for this audience."})
        for field in {"recipient_id", "adviser_id", "level"} - {target_field}:
            if field in attrs:
                raise serializers.ValidationError({field: "Omit this field for the selected audience."})
        return attrs


# Serialize an HOD message without exposing its internal recipient relations.
class HODInboxSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = HODMessage
        fields = ["id", "audience", "subject", "body", "sender_name", "created_at"]
        read_only_fields = fields

    # Prefer the sender's full name, falling back to their username.
    def get_sender_name(self, obj):
        return obj.sender.get_full_name() or obj.sender.username


# Accept the current and replacement credentials for an authenticated password change.
class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


# Validate the email address used to request a password-reset link.
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


# Accept the user identifier, reset token, and replacement password.
class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


# Validate the details needed to create a least-privilege student account.
class StudentAccountCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


# Require the ID of an existing account to link to a student profile.
class StudentAccountLinkSerializer(serializers.Serializer):
    account_id = serializers.IntegerField(min_value=1)
