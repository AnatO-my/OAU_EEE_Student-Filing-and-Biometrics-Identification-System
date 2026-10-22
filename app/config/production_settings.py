"""HTTPS deployment behind a trusted edge, using the explicit PostgreSQL target."""

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .postgres_settings import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a stable random value of at least 50 characters.")

ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if not ALLOWED_HOSTS or any("*" in host or "/" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to explicit deployment hostnames without wildcards or schemes.")

for origin in CSRF_TRUSTED_ORIGINS:  # noqa: F405
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc or "*" in origin or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ImproperlyConfigured("Production CSRF trusted origins must be explicit HTTPS origins.")

if DATABASES["default"]["OPTIONS"]["sslmode"] != "verify-full":  # noqa: F405
    raise ImproperlyConfigured("Production PostgreSQL connections require POSTGRES_SSLMODE=verify-full.")

# Only enable this when the edge overwrites X-Forwarded-Proto and the application
# port cannot be reached directly. The supplied Caddy deployment meets that rule.
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if os.environ.get("DJANGO_TRUST_PROXY_HEADERS", "false").lower() == "true"
    else None
)
USE_X_FORWARDED_HOST = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", str(BASE_DIR.parent / "staticfiles"))  # noqa: F405

# Keep one Gunicorn process for the process-local authentication throttle cache.
# Its two request threads plus one email worker keep ordinary connections well
# below Aiven Free's 20-connection limit. Add shared cache before scaling processes.
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

PASSWORD_RESET_FRONTEND_URL = os.environ.get("PASSWORD_RESET_FRONTEND_URL", "")
if PASSWORD_RESET_FRONTEND_URL:
    reset_url = urlsplit(PASSWORD_RESET_FRONTEND_URL)
    if reset_url.scheme != "https" or not reset_url.netloc:
        raise ImproperlyConfigured("Production PASSWORD_RESET_FRONTEND_URL must use HTTPS.")

# The development module defaults to console delivery. Production must not
# accidentally log password-reset links or queued reports to container output.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND") or "academics.email_backend.EmailBackend"
if EMAIL_BACKEND in {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}:
    raise ImproperlyConfigured("Configure a real email backend for production.")
