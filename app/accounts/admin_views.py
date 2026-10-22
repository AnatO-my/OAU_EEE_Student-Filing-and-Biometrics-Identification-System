"""HOD account administration endpoints; ordinary Django sessions enforce CSRF."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import AcademicSession
from academics.session_context import current_session_name
from .administration import (assignment_data, create_staff, permission_map, require_fresh_hod,
    save_assignment, staff_data, transfer_hod, update_staff)
from .admin_serializers import AssignmentInput, HODTransferInput, StaffCreateInput, StaffUpdateInput
from .models import AdviserAssignment
from .serializers import CurrentUserSerializer


def invoke(action, **kwargs):
    try:
        return action(**kwargs)
    except DjangoValidationError as error:
        raise ValidationError(error.message_dict if hasattr(error, "message_dict")
            else {"non_field_errors": error.messages}) from None


@method_decorator(never_cache, name="dispatch")
class HODAdministrationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.hod = require_fresh_hod(request.user)


class AdministrationOptionsView(HODAdministrationView):
    def get(self, request):
        return Response({"permissions": [{"code": code, "label": permission.name}
            for code, permission in sorted(permission_map().items())],
            "academic_sessions": list(AcademicSession.objects.order_by("name").values("id", "name")),
            "current_academic_session": current_session_name()})


class StaffListView(HODAdministrationView):
    def get(self, request):
        users = get_user_model().objects.filter(is_staff=True).order_by("username", "pk")
        search = request.query_params.get("search", "").strip()
        if len(search) > 150:
            raise ValidationError({"search": "Use at most 150 characters."})
        if search:
            users = users.filter(Q(username__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(email__icontains=search))
        active = request.query_params.get("is_active")
        if active is not None:
            if active not in {"true", "false"}:
                raise ValidationError({"is_active": "Choose true or false."})
            users = users.filter(is_active=active == "true")
        paginator = PageNumberPagination()
        paginator.page_size = 20
        rows = paginator.paginate_queryset(users, request)
        return paginator.get_paginated_response([staff_data(row) for row in rows])

    def post(self, request):
        serializer = StaffCreateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = invoke(create_staff, actor=self.hod, values=serializer.validated_data)
        return Response(staff_data(user), status=201)


class StaffDetailView(HODAdministrationView):
    def patch(self, request, staff_id):
        serializer = StaffUpdateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = invoke(update_staff, actor=self.hod, staff_id=staff_id, values=serializer.validated_data)
        return Response(staff_data(user))


class AdviserAssignmentListView(HODAdministrationView):
    def get(self, request):
        assignments = AdviserAssignment.objects.select_related("staff").order_by("-academic_session", "level", "id")
        if "staff_id" in request.query_params:
            try:
                staff_id = int(request.query_params["staff_id"])
                if staff_id < 1:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValidationError({"staff_id": "Choose a positive staff ID."}) from None
            assignments = assignments.filter(staff_id=staff_id)
        if "academic_session" in request.query_params:
            assignments = assignments.filter(academic_session=request.query_params["academic_session"])
        paginator = PageNumberPagination()
        paginator.page_size = 20
        rows = paginator.paginate_queryset(assignments, request)
        return paginator.get_paginated_response([assignment_data(row) for row in rows])

    def post(self, request):
        serializer = AssignmentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = invoke(save_assignment, actor=self.hod, values=serializer.validated_data)
        return Response(assignment_data(assignment), status=201)


class AdviserAssignmentDetailView(HODAdministrationView):
    def patch(self, request, assignment_id):
        serializer = AssignmentInput(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = invoke(save_assignment, actor=self.hod, assignment_id=assignment_id,
            values=serializer.validated_data)
        return Response(assignment_data(assignment))


class HODTransferView(HODAdministrationView):
    def post(self, request):
        serializer = HODTransferInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        previous, target = invoke(transfer_hod, actor=self.hod, **serializer.validated_data)
        return Response({"user": CurrentUserSerializer(previous).data,
            "target": {"id": target.pk, "username": target.username, "role": "hod"},
            "detail": "HOD ownership transferred. Your account remains active as staff."})
