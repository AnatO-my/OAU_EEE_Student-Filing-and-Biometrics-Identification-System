"""Vercel configuration for an isolated, synthetic demonstration database."""
import os
import ssl
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .production_settings import *  # noqa: F403


if os.environ.get("DEMO_SYNTHETIC_ONLY") != "true":
    raise ImproperlyConfigured("Set DEMO_SYNTHETIC_ONLY=true for the synthetic demonstration.")
if not DATABASES["default"]["NAME"].startswith("eee_demo_"):  # noqa: F405
    raise ImproperlyConfigured("Vercel must use a separate database named eee_demo_..., never the integration database.")
if not os.environ.get("POSTGRES_PASSWORD"):
    raise ImproperlyConfigured("Set the dedicated demo database password.")

_origin = os.environ.get("DEMO_PUBLIC_ORIGIN", "").rstrip("/")
_parsed = urlsplit(_origin)
if (_parsed.scheme != "https" or not _parsed.hostname or _parsed.username or _parsed.password
        or _parsed.path or _parsed.query or _parsed.fragment or "*" in _origin):
    raise ImproperlyConfigured("Set DEMO_PUBLIC_ORIGIN to the exact HTTPS demo origin.")
ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, _parsed.hostname]))  # noqa: F405
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([*CSRF_TRUSTED_ORIGINS, _origin]))  # noqa: F405
_preview_host = os.environ.get("VERCEL_URL", "")
if _preview_host:
    if not _preview_host.endswith(".vercel.app") or any(c in _preview_host for c in "/:@*?# "):
        raise ImproperlyConfigured("VERCEL_URL must be a Vercel deployment hostname.")
    ALLOWED_HOSTS.append(_preview_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_preview_host}")

# Only Vercel's edge invokes this WSGI function. No separately exposed origin
# accepts client-supplied forwarded headers.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 3600
PASSWORD_RESET_FRONTEND_URL = f"{_origin}/reset-password"
STUDENT_ACCOUNT_FRONTEND_ORIGIN = _origin
TEACHING_PORTAL_URL = f"{_origin}/portal"

# Aiven's CA is supplied as an environment secret, not committed to source.
# libpq accepts a certificate path, so materialize only the CA in scratch space.
_ca = os.environ.get("AIVEN_CA_PEM", "")
if _ca:
    try:
        ssl.create_default_context(cadata=_ca)
    except (ssl.SSLError, ValueError):
        raise ImproperlyConfigured("AIVEN_CA_PEM must contain a valid PEM CA certificate.") from None
    with tempfile.NamedTemporaryFile(prefix="eee-aiven-", suffix=".pem", mode="w", delete=False) as _certificate:
        _certificate.write(_ca)
        DATABASES["default"]["OPTIONS"]["sslrootcert"] = _certificate.name  # noqa: F405
elif not Path(DATABASES["default"]["OPTIONS"].get("sslrootcert", "missing-ca-file")).is_file():  # noqa: F405
    raise ImproperlyConfigured("Supply AIVEN_CA_PEM or an existing POSTGRES_SSLROOTCERT file; TLS verification remains required.")

INSTALLED_APPS = [*INSTALLED_APPS, "demo_hosting.apps.DemoHostingConfig"]  # noqa: F405
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "eee_demo_cache",
        "OPTIONS": {"MAX_ENTRIES": 10000},
    }
}
PRIVATE_STORAGE_BACKEND = "demo_hosting.storage.DemoDatabaseStorage"
DEMO_FILE_MAX_BYTES = 3 * 1024 * 1024
DEMO_STORAGE_MAX_BYTES = 50 * 1024 * 1024
DOCUMENT_MAX_UPLOAD_BYTES = DEMO_FILE_MAX_BYTES
TEACHING_MAX_UPLOAD_BYTES = DEMO_FILE_MAX_BYTES
MIDDLEWARE = ["demo_hosting.middleware.DemoRequestLimits", *MIDDLEWARE]  # noqa: F405

# No guardian email, account email or notification delivery starts implicitly.
# A later controlled-recipient session can configure SMTP and explicitly enable
# the appropriate worker against this same isolated database.
if os.environ.get("DEMO_EMAIL_ENABLED") != "true":
    EMAIL_BACKEND = "demo_hosting.email_backend.DisabledEmailBackend"
    RESULT_SHARING_ENABLED = False
