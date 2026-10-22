# Protect all admin actions with the active-superuser policy.
class HODOnlyAdminMixin:
    """Reserve Django admin management screens for active superusers."""

    # Restrict access to the app's admin module to active superusers.
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    # Allow record views only for active superusers.
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    # Allow record creation only for active superusers.
    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    # Allow record changes only for active superusers.
    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    # Allow record deletion only for active superusers.
    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser
