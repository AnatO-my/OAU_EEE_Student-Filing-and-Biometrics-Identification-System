from django.contrib import admin

from accounts.admin_access import HODOnlyAdminMixin
from .models import Guardian, Student


@admin.register(Student)
class StudentAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    pass


@admin.register(Guardian)
class GuardianAdmin(HODOnlyAdminMixin, admin.ModelAdmin):
    pass
