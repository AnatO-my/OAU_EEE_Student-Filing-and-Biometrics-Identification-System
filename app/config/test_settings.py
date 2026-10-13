from .settings import *  # noqa: F403

# Isolated, synthetic tests; no development database is migrated.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
import tempfile  # noqa: E402

PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="test_private_media_")