"""Explicit PostgreSQL settings; never selects the legacy database implicitly."""
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403


# Require connection details needed to reach the configured PostgreSQL server.
def required_database_value(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Set {name} before using config.postgres_settings.")
    return value


try:
    _connect_timeout = int(os.environ.get("POSTGRES_CONNECT_TIMEOUT", "10"))
    if _connect_timeout < 1:
        raise ValueError
except ValueError:
    raise ImproperlyConfigured("POSTGRES_CONNECT_TIMEOUT must be a positive integer.") from None

_postgres_options = {
    "sslmode": os.environ.get("POSTGRES_SSLMODE", "verify-full"),
    "connect_timeout": _connect_timeout,
}
_root_certificate = os.environ.get("POSTGRES_SSLROOTCERT", "").strip()
if _root_certificate:
    _postgres_options["sslrootcert"] = _root_certificate


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_database_value("POSTGRES_DB"),
        "USER": required_database_value("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": required_database_value("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "OPTIONS": _postgres_options,
        "CONN_MAX_AGE": 0,
    }
}
