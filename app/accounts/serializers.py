from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers


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


class CurrentUserSerializer(serializers.ModelSerializer):
    #class that reports the signed in staff member so the frontend can gate its
    #interface, it is only ever read, the frontend never writes through it
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
        ]
        read_only_fields = fields

from .models import AdviserMessage, HODMessage

class AdviserMessageSendSerializer(serializers.Serializer):

    assignment_id = serializers.IntegerField(min_value=1)
    audience = serializers.ChoiceField(
        choices=AdviserMessage.Audience.choices,
    )
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField()
    recipient_id = serializers.UUIDField(required=False)

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

    def get_sender_name(self, obj):
        sender = obj.assignment.staff
        return sender.get_full_name() or sender.username



class HODMessageSendSerializer(serializers.Serializer):
    audience = serializers.ChoiceField(choices=HODMessage.Audience.choices)
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField()
    recipient_id = serializers.UUIDField(required=False)
    adviser_id = serializers.IntegerField(min_value=1, required=False)
    level = serializers.IntegerField(min_value=1, max_value=32767, required=False)

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


class HODInboxSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = HODMessage
        fields = ["id", "audience", "subject", "body", "sender_name", "created_at"]
        read_only_fields = fields

    def get_sender_name(self, obj):
        return obj.sender.get_full_name() or obj.sender.username
