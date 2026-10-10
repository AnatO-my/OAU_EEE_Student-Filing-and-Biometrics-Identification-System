from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from students.models import Student

from .calculations import calculate_student_cgpa, calculate_student_gpa
from .models import AcademicSession, Course, CourseOffering, GradingScale, Result, CourseRequirement, GraduationReview
from .serializers import (
    ResultCreateSerializer,
    ResultScoreUpdateSerializer,
    ResultSerializer,
    ResultVerifySerializer,
    ResultFilterSerializer,
    StudentGPAQuerySerializer,
    AcademicSessionSerializer,
    CourseSerializer,
    CourseOfferingSerializer,
    CourseRequirementSerializer, GraduationApprovalSerializer, GraduationReviewSerializer,
    GradingScaleWriteSerializer, GradingScaleSerializer, OfferingScaleSerializer,
)
from .services import (
    create_result, update_result_score, verify_result,
    create_grading_scale, update_grading_scale, publish_grading_scale,
    assign_offering_scale,
)
from .access import ResultAccessPermission, academic_students_for


def results_for(user):
    return Result.objects.filter(student__in=academic_students_for(user))


class IsActiveHOD(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and user.is_active
            and user.is_staff
            and user.is_superuser
        )


class ResultPagination(PageNumberPagination):
    page_size = 20


class ResultCreateView(APIView):
    permission_classes = [ResultAccessPermission]

    def post(self, request):
        serializer = ResultCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        try:
            result = create_result(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError({"non_field_errors": exc.messages}) from exc

        return Response(
            ResultSerializer(result).data,
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        filters = ResultFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data

        results = results_for(request.user).select_related("student", "offering").order_by("pk")

        if "student_id" in values:
            results = results.filter(student_id=values["student_id"])

        if "academic_session" in values:
            results = results.filter(
                offering__academic_session__name=(values["academic_session"])
            )

        if "semester" in values:
            results = results.filter(offering__semester=values["semester"])

        if "is_verified" in values:
            results = results.filter(is_verified=values["is_verified"])

        paginator = ResultPagination()
        page = paginator.paginate_queryset(results, request)
        serializer = ResultSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class ResultScoreUpdateView(APIView):
    permission_classes = [ResultAccessPermission]

    def patch(self, request, result_id):
        result = get_object_or_404(results_for(request.user), pk=result_id)

        serializer = ResultScoreUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = update_result_score(
                user=request.user,
                result=result,
                score=serializer.validated_data["score"],
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError({"non_field_errors": exc.messages}) from exc

        return Response(ResultSerializer(result).data)

    def get(self, request, result_id):
        result = get_object_or_404(
            results_for(request.user).select_related(
                "student",
                "offering",
            ),
            pk=result_id,
        )

        return Response(ResultSerializer(result).data)


class ResultVerifyView(APIView):
    permission_classes = [ResultAccessPermission]
    result_action = "verify_result"

    def post(self, request, result_id):
        result = get_object_or_404(results_for(request.user), pk=result_id)

        serializer = ResultVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = verify_result(
                user=request.user,
                result=result,
                expected_score=serializer.validated_data["expected_score"],
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError({"non_field_errors": exc.messages}) from exc

        return Response(ResultSerializer(result).data)


class StudentGPAView(APIView):
    permission_classes = [ResultAccessPermission]

    def get(self, request, student_id):
        student = get_object_or_404(academic_students_for(request.user), pk=student_id)

        query = StudentGPAQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        academic_session = query.validated_data["academic_session"]
        semester = query.validated_data["semester"]

        try:
            gpa = calculate_student_gpa(
                student=student,
                academic_session=academic_session,
                semester=semester,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError({"non_field_errors": exc.messages}) from exc

        return Response(
            {
                "student_id": str(student.pk),
                "academic_session": academic_session.name,
                "semester": semester,
                "gpa": str(gpa) if gpa is not None else None,
            }
        )


class StudentCGPAView(APIView):
    permission_classes = [ResultAccessPermission]

    def get(self, request, student_id):
        student = get_object_or_404(academic_students_for(request.user), pk=student_id)
        try:
            cgpa = calculate_student_cgpa(student=student)
        except DjangoValidationError as exc:
            raise ValidationError({"non_field_errors": exc.messages}) from exc
        completeness = "not_confirmed"
        review = GraduationReview.objects.filter(student=student).first()
        if review:
            from .graduation import reviewed_history
            try:
                _, digest = reviewed_history(student)
                completeness = "hod_reviewed" if digest == review.history_digest else "review_required"
            except (DjangoValidationError, ValidationError):
                completeness = "review_required"
        return Response({
            "student_id": str(student.pk),
            "cgpa": str(cgpa) if cgpa is not None else None,
            "history_completeness": completeness,
        })


def own_student(request):
    # Never accept a student identifier supplied by the client here.
    return get_object_or_404(
        Student, user=request.user, user__is_active=True,
        user__is_staff=False,
    )


class MyGPAView(StudentGPAView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        student = own_student(request)
        return super().get(request, student.pk)


class MyCGPAView(StudentCGPAView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        student = own_student(request)
        return super().get(request, student.pk)


class MyResultsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResultSerializer
    pagination_class = ResultPagination

    def get_queryset(self):
        student = own_student(self.request)
        return student.results.filter(is_verified=True).order_by("pk")


class MyResultDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResultSerializer
    lookup_url_kwarg = "result_id"

    def get_queryset(self):
        student = own_student(self.request)
        return student.results.filter(is_verified=True)


class AcademicSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveHOD]
    serializer_class = AcademicSessionSerializer
    pagination_class = ResultPagination
    queryset = AcademicSession.objects.order_by("name")


class CourseListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveHOD]
    serializer_class = CourseSerializer
    pagination_class = ResultPagination
    queryset = Course.objects.order_by("code")


class CourseOfferingListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveHOD]
    serializer_class = CourseOfferingSerializer
    pagination_class = ResultPagination
    queryset = CourseOffering.objects.select_related("course", "academic_session").order_by("pk")


# Translate model/service validation consistently to JSON 400 responses.
def run_academic_service(service, **kwargs):
    try:
        return service(**kwargs)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
        raise ValidationError(detail) from exc


class GradingScaleListCreateView(APIView):
    permission_classes = [IsActiveHOD]

    def get(self, request):
        paginator = ResultPagination()
        page = paginator.paginate_queryset(GradingScale.objects.order_by("pk"), request)
        return paginator.get_paginated_response(GradingScaleSerializer(page, many=True).data)

    def post(self, request):
        serializer = GradingScaleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scale = run_academic_service(create_grading_scale, user=request.user,
                                     validated_data=serializer.validated_data)
        return Response(GradingScaleSerializer(scale).data, status=status.HTTP_201_CREATED)


class GradingScaleDetailView(APIView):
    permission_classes = [IsActiveHOD]

    def get(self, request, scale_id):
        return Response(GradingScaleSerializer(get_object_or_404(GradingScale, pk=scale_id)).data)

    def patch(self, request, scale_id):
        scale = get_object_or_404(GradingScale, pk=scale_id)
        serializer = GradingScaleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        scale = run_academic_service(update_grading_scale, user=request.user,
                                     scale=scale, validated_data=serializer.validated_data)
        return Response(GradingScaleSerializer(scale).data)


class GradingScalePublishView(APIView):
    permission_classes = [IsActiveHOD]

    def post(self, request, scale_id):
        scale = run_academic_service(publish_grading_scale, user=request.user,
                                    scale=get_object_or_404(GradingScale, pk=scale_id))
        return Response(GradingScaleSerializer(scale).data)


class OfferingScaleUpdateView(APIView):
    permission_classes = [IsActiveHOD]

    def patch(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        serializer = OfferingScaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offering = run_academic_service(assign_offering_scale, user=request.user,
            offering=offering, scale=serializer.validated_data["grading_scale"])
        return Response(CourseOfferingSerializer(offering).data)


class CourseRequirementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveHOD]
    serializer_class = CourseRequirementSerializer
    pagination_class = ResultPagination

    def parent(self):
        return get_object_or_404(Student, pk=self.kwargs["student_id"])

    def get_queryset(self):
        return self.parent().course_requirements.order_by("pk")

    def perform_create(self, serializer):
        from .graduation import save_course_requirement
        serializer.instance = run_academic_service(save_course_requirement,
            user=self.request.user, student=self.parent(), validated_data=serializer.validated_data)


class CourseRequirementDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsActiveHOD]
    serializer_class = CourseRequirementSerializer
    lookup_url_kwarg = "requirement_id"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return CourseRequirement.objects.filter(student_id=self.kwargs["student_id"])

    def perform_update(self, serializer):
        from .graduation import save_course_requirement
        serializer.instance = run_academic_service(save_course_requirement,
            user=self.request.user, student=serializer.instance.student,
            requirement=serializer.instance, validated_data=serializer.validated_data)


class GraduationReviewView(APIView):
    permission_classes = [IsActiveHOD]

    def get(self, request, student_id):
        from .graduation import reviewed_history
        from django.db import transaction
        # Same student lock used by every academic mutation service.
        with transaction.atomic():
            student = get_object_or_404(Student.objects.select_for_update(), pk=student_id)
            cgpa, digest = run_academic_service(reviewed_history, student=student)
            review = GraduationReview.objects.filter(student=student).first()
            return Response({"student_id": str(student.pk), "cgpa": str(cgpa),
                "history_digest": digest, "review_current": bool(review and review.history_digest == digest),
                "review": GraduationReviewSerializer(review).data if review else None})

    def post(self, request, student_id):
        from .graduation import approve_graduation
        student = get_object_or_404(Student, pk=student_id)
        serializer = GraduationApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = run_academic_service(approve_graduation, user=request.user, student=student,
            notes=serializer.validated_data["notes"], expected_digest=serializer.validated_data["expected_digest"])
        return Response(GraduationReviewSerializer(review).data)
