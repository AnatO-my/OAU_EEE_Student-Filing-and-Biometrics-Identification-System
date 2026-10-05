from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, AdviserAssignment
from .admin_access import HODOnlyAdminMixin

@admin.register(User)
class StaffUserAdmin(HODOnlyAdminMixin, UserAdmin):
    pass


@admin.register(AdviserAssignment)
class AdviserAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "staff",
        "academic_session",
        "level",
        "is_active",
    ]
    list_filter = ["academic_session", "level", "is_active"]
    search_fields = ["staff__username", "staff__first_name", "staff__last_name"]

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False
