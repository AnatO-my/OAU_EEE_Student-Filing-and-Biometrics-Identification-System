from rest_framework import serializers
from django.core.exceptions import ValidationError as ModelValidationError

from .models import Student, Guardian
from .identity import identifier_key


# Expose the student profile fields used by list and detail endpoints.
class IdentifierValueField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Student identifiers must be supplied as text.")
        return super().to_internal_value(data)


class StudentSerializer(serializers.ModelSerializer):
    surname = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=100)
    identifier_value = IdentifierValueField(max_length=100)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=30)

    def validate_identifier_value(self, value):
        try:
            identifier_key(value)
        except ModelValidationError as error:
            raise serializers.ValidationError(error.messages) from None
        return value.strip()

    # Bind this serializer to Student and limit its API representation.
    class Meta:
        model = Student
        fields = [
            "student_id",
            "identifier_type",
            "identifier_value",
            "full_name",
            "surname",
            "phone_number",
            "admission_year",
            "mode_of_admission",
            "current_level",
            "is_active",
            "academic_status",
        ]
        read_only_fields = ["student_id"]


class StudentLookupSerializer(serializers.Serializer):
    identifier_type = serializers.ChoiceField(choices=Student.IdentifierType.choices)
    identifier_value = IdentifierValueField(max_length=100)

    def validate_identifier_value(self, value):
        try:
            identifier_key(value)
        except ModelValidationError as error:
            raise serializers.ValidationError(error.messages) from None
        return value.strip()


class StudentIdentifierPromotionSerializer(StudentLookupSerializer):
    identifier_type = None
    expected_identifier_type = serializers.ChoiceField(choices=Student.IdentifierType.choices)
    expected_identifier_value = IdentifierValueField(max_length=100)


# Serialize a guardian record and its associated student reference.
class GuardianSerializer(serializers.ModelSerializer):
    # Bind guardian fields while keeping the generated identifier immutable.
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


# Validate optional query-string filters for the student list endpoint.
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


# Validate HOD bulk level changes and reject duplicate student identifiers.
class BulkStudentLevelSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=1000,
    )
    expected_level = serializers.IntegerField(min_value=1, max_value=32767)
    current_level = serializers.IntegerField(min_value=1, max_value=32767)

    # Avoid applying a requested bulk operation more than once per student.
    def validate_student_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Each student ID must appear only once.")
        return value

# Validate bulk academic-status changes and require a new destination status.
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

    # Ensure each student appears once in the requested bulk operation.
    def validate_student_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Each student ID must appear only once."
            )
        return value

    # Disallow bulk status changes that would leave every status unchanged.
    def validate(self, attrs):
        if attrs["expected_status"] == attrs["academic_status"]:
            raise serializers.ValidationError({
                "academic_status": "Choose a different destination status."
            })
        return attrs


# Prevent guardian API clients from selecting or reassigning the parent student.
class ScopedGuardianSerializer(GuardianSerializer):
    # Keep both the guardian ID and parent link server-controlled.
    class Meta(GuardianSerializer.Meta):
        read_only_fields = ["guardian_id", "student"]
