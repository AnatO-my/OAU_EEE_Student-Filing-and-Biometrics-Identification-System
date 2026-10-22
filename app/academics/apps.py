from django.apps import AppConfig


# Configure Django's academics application and default model primary-key type.
class AcademicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'academics'
