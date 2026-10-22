from decimal import Decimal

from rest_framework import serializers

from students.models import Student

from .models import AcademicSession, Course, CourseOffering, GradingScale, Result, CourseRequirement, GraduationReview
from .access import academic_students_for
from .grading import validate_bands


# Validate result creation and scope selectable students to the authenticated requester.
class ResultCreateSerializer(serializers.Serializer):
    # Narrow student choices to records the request user may access.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            self.fields["student_id"].queryset = academic_students_for(request.user)

    student_id = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(),
        source="student",
    )
    offering_id = serializers.PrimaryKeyRelatedField(
        queryset=CourseOffering.objects.all(),
        source="offering",
    )
    attempt_number = serializers.IntegerField(
        min_value=1,
        max_value=32767,
        default=1,
    )
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        allow_null=True,
        default=None,
    )


# Return result fields as read-only data for review and reporting endpoints.
class ResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Result
        fields = [
            "id",
            "student",
            "offering",
            "attempt_number",
            "score",
            "credit_units",
            "is_verified",
            "grading_scale",
        ]
        read_only_fields = fields


# Accept a required score correction, including an explicit null to clear the score.
class ResultScoreUpdateSerializer(serializers.Serializer):
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=True,
        allow_null=True,
    )


# Require the score value the reviewer actually checked before verification.
class ResultVerifySerializer(serializers.Serializer):
    expected_score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=True,
        allow_null=False,
    )


# Validate optional result-list filters and enforce consecutive academic-year boundaries.
class ResultFilterSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=False)

    academic_session = serializers.RegexField(
        regex=r"^[0-9]{4}/[0-9]{4}$",
        required=False,
    )

    semester = serializers.ChoiceField(
        choices=CourseOffering.Semester.choices,
        required=False,
    )

    is_verified = serializers.BooleanField(required=False)

    # Reject academic years whose second year does not immediately follow the first.
    def validate_academic_session(self, value):
        first_year, second_year = map(int, value.split("/"))

        if second_year != first_year + 1:
            raise serializers.ValidationError(
                "The second year must immediately follow the first."
            )

        return value

# Resolve a requested session and semester for GPA calculation.
class StudentGPAQuerySerializer(serializers.Serializer):
    academic_session = serializers.SlugRelatedField(
        slug_field="name",
        queryset=AcademicSession.objects.all(),
        required=True,
    )
    semester = serializers.ChoiceField(
        choices=CourseOffering.Semester.choices,
        required=True,
    )


# Serialize academic sessions and reuse model rules for session-name validation.
class AcademicSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicSession
        fields = ["id", "name"]
        read_only_fields = ["id"]

    # Apply AcademicSession's calendar-year validation to incoming API values.
    def validate_name(self, value):
        session = AcademicSession(name=value)
        from django.core.exceptions import ValidationError as ModelValidationError
        try:
            session.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict["name"]) from exc
        return value


# Expose catalogue courses while keeping generated IDs read-only.
class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "code", "title"]
        read_only_fields = ["id"]


# Serialize teaching-period offerings and permit only published grading versions.
class CourseOfferingSerializer(serializers.ModelSerializer):
    grading_scale = serializers.PrimaryKeyRelatedField(
        queryset=GradingScale.objects.filter(is_published=True), required=False,
    )

    class Meta:
        model = CourseOffering
        fields = ["id", "course", "academic_session", "semester", "level", "credit_units", "grading_scale"]
        read_only_fields = ["id"]


# Validate editable scale names and normalize fully validated grading bands.
class GradingScaleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    bands = serializers.ListField(child=serializers.JSONField(), allow_empty=False)

    # Reuse grading rules and emit decimal values in a stable JSON-safe representation.
    def validate_bands(self, value):
        from django.core.exceptions import ValidationError as ModelValidationError
        try:
            parsed = validate_bands(value)
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict["bands"]) from exc
        return [{"minimum": str(low), "maximum": str(high), "grade_point": str(points)}
                for low, high, points in parsed]


# Expose all grading-version fields as read-only API data.
class GradingScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingScale
        fields = ["id", "name", "bands", "is_published"]
        read_only_fields = fields


# Require the published scale to assign to an offering.
class OfferingScaleSerializer(serializers.Serializer):
    grading_scale = serializers.PrimaryKeyRelatedField(
        queryset=GradingScale.objects.filter(is_published=True)
    )


# Serialize course requirements while reserving student and recorder fields for the server.
class CourseRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseRequirement
        fields = ["id", "student", "offering", "resolution", "reason", "recorded_by"]
        read_only_fields = ["id", "student", "recorded_by"]


# Validate approval evidence and explicit HOD confirmations before graduation review.
class GraduationApprovalSerializer(serializers.Serializer):
    notes = serializers.CharField()
    expected_digest = serializers.RegexField(regex=r"^[a-f0-9]{64}$")
    history_complete = serializers.BooleanField()
    other_requirements_satisfied = serializers.BooleanField()

    # Require affirmative confirmation of both history and non-academic requirements.
    def validate(self, attrs):
        if not attrs["history_complete"] or not attrs["other_requirements_satisfied"]:
            raise serializers.ValidationError("The HOD must confirm complete history and other graduation requirements.")
        return attrs


# Return stored HOD review snapshots without allowing client-side changes.
class GraduationReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = GraduationReview
        fields = ["student", "reviewed_by", "reviewed_at", "notes", "cgpa_snapshot"]
        read_only_fields = fields
