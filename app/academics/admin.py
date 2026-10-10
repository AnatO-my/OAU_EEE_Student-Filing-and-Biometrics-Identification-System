from django.contrib import admin

from accounts.admin_access import HODOnlyAdminMixin
from .models import GradingScale


@admin.register(GradingScale)
class GradingScaleAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["name", "is_published"]
    readonly_fields = ["name", "bands", "is_published"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
