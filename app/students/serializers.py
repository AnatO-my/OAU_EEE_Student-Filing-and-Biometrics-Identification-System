from rest_framework import serializers

from .models import Student, Guardian


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "student_id",
            "identifier_type",
            "identifier_value",
            "full_name",
            "phone_number",
            "admission_year",
            "mode_of_admission",
            "current_level",
            "is_active",
        ]
        read_only_fields = ["student_id"]


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = [
            "guardian_id",
            "student",
            "full_name",
            "phone_number",
            "relationship",
            "email",
            "address",
        ]
        read_only_fields = ["guardian_id"]


class StudentFilterSerializer(serializers.Serializer):
    admission_year = serializers.IntegerField(
        min_value=0,
        max_value=32767,
        required=False,
    )
    current_level = serializers.IntegerField(
        min_value=0,
        max_value=32767,
        required=False,
    )
    mode_of_admission = serializers.ChoiceField(
        choices=Student.AdmissionMode.choices,
        required=False,
    )
    identifier_type = serializers.ChoiceField(
        choices=Student.IdentifierType.choices,
        required=False,
    )
    is_active = serializers.BooleanField(required=False)
