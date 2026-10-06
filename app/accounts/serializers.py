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