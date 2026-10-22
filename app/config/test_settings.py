from .settings import *  # noqa: F403
from .test_media import PRIVATE_MEDIA_ROOT  # noqa: F401

# Isolated, synthetic tests; no development database is migrated.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
