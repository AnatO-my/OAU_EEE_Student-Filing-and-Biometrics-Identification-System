"""Disposable PostgreSQL tests using the same verified TLS settings as the app."""

from .postgres_settings import *  # noqa: F403
from .test_media import PRIVATE_MEDIA_ROOT  # noqa: F401

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
