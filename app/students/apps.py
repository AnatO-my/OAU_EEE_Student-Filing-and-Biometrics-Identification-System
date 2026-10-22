from django.apps import AppConfig


# Register the students application and its default primary-key type.
class StudentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'students'
