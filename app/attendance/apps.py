from django.apps import AppConfig


# Configure the attendance Django app and its default database key type.
class AttendanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "attendance"
