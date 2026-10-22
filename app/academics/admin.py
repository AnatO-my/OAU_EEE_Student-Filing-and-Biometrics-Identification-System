from django.contrib import admin

from accounts.admin_access import HODOnlyAdminMixin
from .models import GradingScale


@admin.register(GradingScale)
# Keep grading-scale records visible in admin but immutable outside the service workflow.
class GradingScaleAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["name", "is_published"]
    readonly_fields = ["name", "bands", "is_published"]

    # Published and draft scales are created through validated academic services instead.
    def has_add_permission(self, request):
        return False

    # Prevent direct admin edits from bypassing publication and immutability rules.
    def has_change_permission(self, request, obj=None):
        return False

    # Preserve grading versions referenced by offerings and historical results.
    def has_delete_permission(self, request, obj=None):
        return False


from django.contrib import messages
from .models import AcademicSession, CurrentAcademicSession
from .current_session import select_current_session


@admin.register(AcademicSession)
# Expose session records with a controlled action for selecting the current session.
class AcademicSessionAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["name"]
    actions = ["make_current"]

    @admin.action(description="Set the selected academic session as current", permissions=["view"])
    # Require exactly one selected session and use the optimistic current-session check.
    def make_current(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one academic session.", messages.ERROR)
            return
        selection = CurrentAcademicSession.objects.get(pk=1)
        select_current_session(user=request.user, academic_session=queryset.get(),
            expected_session_id=selection.academic_session_id)
        self.message_user(request, "Current academic session updated. Existing assignments and classes were preserved.")

    # Retain referenced academic sessions for assignments and results.
    def has_delete_permission(self, request, obj=None):
        return False

    # Session names are referenced by assignments; select a new session instead of editing.
    def has_change_permission(self, request, obj=None):
        # Names are referenced by adviser assignments; create a new session instead.
        return False
