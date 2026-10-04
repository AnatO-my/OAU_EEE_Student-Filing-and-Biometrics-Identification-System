from django.contrib import admin

from .models import Guardian, Student

admin.site.register(Student)
admin.site.register(Guardian)
