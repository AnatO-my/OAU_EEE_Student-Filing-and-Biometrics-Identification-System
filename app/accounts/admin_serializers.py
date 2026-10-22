"""Explicit input fields for HOD account administration; credentials are write-only."""
from collections.abc import Mapping

from rest_framework import serializers


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "This field cannot be changed here." for key in unknown})
        return super().to_internal_value(data)


class StaffCreateInput(StrictInput):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    first_name = serializers.CharField(max_length=150, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, allow_blank=True, default="")
    email = serializers.EmailField(allow_blank=True, default="")
    is_active = serializers.BooleanField(default=True)
    permission_codes = serializers.ListField(child=serializers.CharField(max_length=100), max_length=40, default=list)


class StaffUpdateInput(StrictInput):
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)
    permission_codes = serializers.ListField(child=serializers.CharField(max_length=100), max_length=40, required=False)


class AssignmentInput(StrictInput):
    staff_id = serializers.IntegerField(min_value=1)
    academic_session = serializers.CharField(max_length=9)
    level = serializers.IntegerField(min_value=1, max_value=32767)
    is_active = serializers.BooleanField(default=True)


class HODTransferInput(StrictInput):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    target_staff_id = serializers.IntegerField(min_value=1)
    expected_target_username = serializers.CharField(max_length=150)
    confirmation = serializers.ChoiceField(choices=["TRANSFER HOD"])
