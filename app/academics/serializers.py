from decimal import Decimal

from rest_framework import serializers

from students.models import Student

from .models import AcademicSession, Course, CourseOffering, GradingScale, Result, CourseRequirement, GraduationReview
from .access import academic_students_for
from .grading import validate_bands


class ResultCreateSerializer(serializers.Serializer):
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


class ResultScoreUpdateSerializer(serializers.Serializer):
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=True,
        allow_null=True,
    )


class ResultVerifySerializer(serializers.Serializer):
    expected_score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=True,
        allow_null=False,
    )


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

    def validate_academic_session(self, value):
        first_year, second_year = map(int, value.split("/"))

        if second_year != first_year + 1:
            raise serializers.ValidationError(
                "The second year must immediately follow the first."
            )

        return value

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


class AcademicSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicSession
        fields = ["id", "name"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        session = AcademicSession(name=value)
        from django.core.exceptions import ValidationError as ModelValidationError
        try:
            session.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict["name"]) from exc
        return value


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "code", "title"]
        read_only_fields = ["id"]


class CourseOfferingSerializer(serializers.ModelSerializer):
    grading_scale = serializers.PrimaryKeyRelatedField(
        queryset=GradingScale.objects.filter(is_published=True), required=False,
    )

    class Meta:
        model = CourseOffering
        fields = ["id", "course", "academic_session", "semester", "level", "credit_units", "grading_scale"]
        read_only_fields = ["id"]


class GradingScaleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    bands = serializers.ListField(child=serializers.JSONField(), allow_empty=False)

    def validate_bands(self, value):
        from django.core.exceptions import ValidationError as ModelValidationError
        try:
            parsed = validate_bands(value)
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict["bands"]) from exc
        return [{"minimum": str(low), "maximum": str(high), "grade_point": str(points)}
                for low, high, points in parsed]


class GradingScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingScale
        fields = ["id", "name", "bands", "is_published"]
        read_only_fields = fields


class OfferingScaleSerializer(serializers.Serializer):
    grading_scale = serializers.PrimaryKeyRelatedField(
        queryset=GradingScale.objects.filter(is_published=True)
    )


class CourseRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseRequirement
        fields = ["id", "student", "offering", "resolution", "reason", "recorded_by"]
        read_only_fields = ["id", "student", "recorded_by"]


class GraduationApprovalSerializer(serializers.Serializer):
    notes = serializers.CharField()
    expected_digest = serializers.RegexField(regex=r"^[a-f0-9]{64}$")
    history_complete = serializers.BooleanField()
    other_requirements_satisfied = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs["history_complete"] or not attrs["other_requirements_satisfied"]:
            raise serializers.ValidationError("The HOD must confirm complete history and other graduation requirements.")
        return attrs


class GraduationReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = GraduationReview
        fields = ["student", "reviewed_by", "reviewed_at", "notes", "cgpa_snapshot"]
        read_only_fields = fields
