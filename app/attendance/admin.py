from django.contrib import admin
from accounts.admin_access import HODOnlyAdminMixin
from .models import (AttendanceSession, AttendanceRecord, AttendanceEvent,
                     AttendanceCorrection, CourseRoster, CourseStaffAssignment, CourseRosterApproval)


# Restrict attendance records in Django admin to read-only HOD access.
class AttendanceReadOnlyAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    # Attendance data is managed through the audited application workflows.
    def has_add_permission(self, request):
        return False

    # Prevent direct edits that would bypass attendance correction history.
    def has_change_permission(self, request, obj=None):
        return False

    # Keep related attendance and roster records available for audit.
    def has_delete_permission(self, request, obj=None):
        return False


for model in (AttendanceSession, AttendanceRecord, AttendanceEvent,
              AttendanceCorrection, CourseRoster, CourseStaffAssignment, CourseRosterApproval):
    admin.site.register(model, AttendanceReadOnlyAdmin)
