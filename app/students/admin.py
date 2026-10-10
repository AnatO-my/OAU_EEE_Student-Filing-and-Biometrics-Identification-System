from django.contrib import admin
from django.db import transaction

from accounts.admin_access import HODOnlyAdminMixin
from .models import Guardian, Student


@admin.register(Student)
class StudentAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    # These actions must use the reviewed graduation/account services.
    readonly_fields = ["academic_status", "user"]

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj and obj.academic_status == Student.AcademicStatus.GRADUATED:
            fields += ["current_level", "admission_year", "mode_of_admission"]
        return fields


@admin.register(Guardian)
class GuardianAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return ["student"] if obj else []

    def save_model(self, request, obj, form, change):
        # Match guardian API locking so result delivery cannot race contact edits.
        with transaction.atomic():
            Student.objects.select_for_update().get(pk=obj.student_id)
            super().save_model(request, obj, form, change)
