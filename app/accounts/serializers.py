from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from .models import AdviserMessage, HODMessage


class LoginSerializer(serializers.Serializer):
    # class for validating the credentials posted by a staff member, the password is
    # write only so it can never be read back out of a serialised representation
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    # method that checks the credentials and rejects anything that is not a staff
    # account, a student record does not imply a login account
    def validate(self, attrs):
        request = self.context.get("request")
        django_request = getattr(request, "_request", None)

        user = authenticate(
            request=django_request,
            username=attrs["username"],
            password=attrs["password"],
        )

        # the same error is raised for an unknown username, a wrong password, and a
        # non staff account so the endpoint cannot be used to discover which staff
        # accounts exist
        if user is None or not user.is_active or not user.is_staff:
            raise serializers.ValidationError("Invalid username or password.")

        attrs["user"] = user
        return attrs


class CurrentUserSerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = fields


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


class HODMessageSerializer(serializers.Serializers):
    assignment_id = serializers.ntergerField(min_value=1)
    audience = serializers.ChoiceField(
        choices=HODMessage.Audience.choices,
    )


subject = serializers.CharField(max_length=200)
body = serializers.CharField()
reciepent_id = serializers.UUIDField(required=False)


def validate(self, attrs):
    audience = attrs["audience"]
    recipient_id = attrs.get("receipient_id")

    if audience == HODMessage.Audience.ADVISER:
        if recipient_id is None:
            raise serializers.ValidationError(
                {"recipient_id": "Select a part adviser for an indivdual message."}
            )
        elif recipient_id is not None:
            raise serializers.ValidationError(
                {
                    "recipient_id": (
                        "Omit this field for a general announcement"
                        "The backend select the recipients."
                    )
                }
            )
    return attrs
