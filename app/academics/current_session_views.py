from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import AcademicSession, CurrentAcademicSession
from .current_session import current_session_name, select_current_session
from .views import IsActiveHOD, run_academic_service


# Validate a session choice together with the current value the client reviewed.
class SelectionSerializer(serializers.Serializer):
    academic_session = serializers.PrimaryKeyRelatedField(queryset=AcademicSession.objects.all())
    expected_session_id = serializers.IntegerField(allow_null=True, min_value=1)


# Expose the current academic session to HODs and accept guarded session changes.
class CurrentSessionView(APIView):
    permission_classes = [IsActiveHOD]

    # Report both the selected session and whether it came from the database or environment.
    def get(self, request):
        row = CurrentAcademicSession.objects.filter(pk=1).first()
        return Response({"academic_session": row.academic_session_id if row else None,
            "name": current_session_name(), "source": "database" if row and row.academic_session_id else "environment"})

    # Validate and apply the HOD's session selection, then return the updated representation.
    def put(self, request):
        serializer = SelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(select_current_session, user=request.user, **serializer.validated_data)
        return self.get(request)
