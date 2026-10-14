"""Explicit PostgreSQL settings; never selects the legacy database implicitly."""
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403


def required_database_value(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Set {name} before using config.postgres_settings.")
    return value


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_database_value("POSTGRES_DB"),
        "USER": required_database_value("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": required_database_value("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "OPTIONS": {"sslmode": os.environ.get("POSTGRES_SSLMODE", "verify-full")},
        "CONN_MAX_AGE": 0,
    }
}
