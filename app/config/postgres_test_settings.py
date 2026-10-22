"""Disposable PostgreSQL tests using the same verified TLS settings as the app."""

from .postgres_settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
