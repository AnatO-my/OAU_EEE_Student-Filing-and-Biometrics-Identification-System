from django.apps import AppConfig


# Register the accounts app and its default primary-key field type.
class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
