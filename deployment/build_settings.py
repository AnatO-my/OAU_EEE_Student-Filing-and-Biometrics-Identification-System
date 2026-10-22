"""Static-file collection only: no network, real database or runtime secret."""
import os

from config.settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}
STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", "/srv/static")
RESULT_SHARING_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
