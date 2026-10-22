from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import AcademicSession
from .current_session import current_session_state, select_current_session
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
        return Response(current_session_state())

    # Validate and apply the HOD's session selection, then return the updated representation.
    def put(self, request):
        serializer = SelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_academic_service(select_current_session, user=request.user, **serializer.validated_data)
        return self.get(request)
