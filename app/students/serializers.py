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
            "academic_status",
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


class BulkStudentLevelSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=1000,
    )
    expected_level = serializers.IntegerField(min_value=1, max_value=32767)
    current_level = serializers.IntegerField(min_value=1, max_value=32767)

    def validate_student_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Each student ID must appear only once.")
        return value

class BulkStudentStatusSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=1000,
    )
    expected_status = serializers.ChoiceField(
        choices=Student.AcademicStatus.choices,
    )
    academic_status = serializers.ChoiceField(
        choices=Student.AcademicStatus.choices,
    )

    def validate_student_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Each student ID must appear only once."
            )
        return value

    def validate(self, attrs):
        if attrs["expected_status"] == attrs["academic_status"]:
            raise serializers.ValidationError({
                "academic_status": "Choose a different destination status."
            })
        return attrs


class ScopedGuardianSerializer(GuardianSerializer):
    class Meta(GuardianSerializer.Meta):
        read_only_fields = ["guardian_id", "student"]
