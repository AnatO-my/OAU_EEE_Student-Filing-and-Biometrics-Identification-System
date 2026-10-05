from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    #class for validating the credentials posted by a staff member, the password is
    #write only so it can never be read back out of a serialised representation
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    #method that checks the credentials and rejects anything that is not a staff
    #account, a student record does not imply a login account
    def validate(self, attrs):
        request = self.context.get("request")
        django_request = getattr(request, "_request", None)

        user = authenticate(
            request=django_request,
            username=attrs["username"],
            password=attrs["password"],
        )

        #the same error is raised for an unknown username, a wrong password, and a
        #non staff account so the endpoint cannot be used to discover which staff
        #accounts exist
        if user is None or not user.is_active or not user.is_staff:
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