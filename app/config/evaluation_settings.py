"""Opt-in isolated rehearsal settings. Never used by the normal launcher."""
import json
import os
from pathlib import Path

_eval_raw_root = os.environ.get("EEE_EVALUATION_ROOT")
if not _eval_raw_root:
    raise RuntimeError("EEE_EVALUATION_ROOT must identify a separately initialized scratch run.")
EVALUATION_ROOT = Path(_eval_raw_root).resolve(strict=True)
_eval_marker_path = EVALUATION_ROOT / "evaluation-scratch.json"
_eval_marker = json.loads(_eval_marker_path.read_text(encoding="utf-8"))
if (_eval_marker.get("purpose") != "EEE_ISOLATED_EVALUATION"
        or _eval_marker.get("root") != str(EVALUATION_ROOT)
        or _eval_marker.get("schema_version") != 1):
    raise RuntimeError("Refusing an unrecognized scratch run.")
for _name in ("scratch.sqlite3", "private-media", "session-secret.txt"):
    if (EVALUATION_ROOT / _name).resolve().parent != EVALUATION_ROOT:
        raise RuntimeError("Scratch paths must remain inside their initialized run.")
# Force safe bootstrap before importing settings, even if the operator has a
# production environment configured. Every persistence/transport setting is
# replaced below; no DATABASE_URL or SMTP environment value is honored.
os.environ["DJANGO_DEBUG"] = "true"
from .settings import *  # noqa: F403,E402
DEBUG = True
SECRET_KEY = (EVALUATION_ROOT / "session-secret.txt").read_text(encoding="utf-8").strip()
if len(SECRET_KEY) < 40:
    raise RuntimeError("The scratch session key is missing or invalid.")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(EVALUATION_ROOT / "scratch.sqlite3")}}
PRIVATE_MEDIA_ROOT = str(EVALUATION_ROOT / "private-media")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = ""
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
DEFAULT_FROM_EMAIL = "evaluation@example.invalid"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5175", "http://localhost:5175"]
SESSION_COOKIE_NAME = "eee_eval_" + _eval_marker["run_id"].replace("-", "")[:16]
CSRF_COOKIE_NAME = SESSION_COOKIE_NAME + "_csrf"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
CURRENT_ACADEMIC_SESSION = "2026/2027"
TEACHING_PORTAL_URL = "http://127.0.0.1:5175/portal"
PASSWORD_RESET_FRONTEND_URL = "http://127.0.0.1:5175/reset-password"
STUDENT_ACCOUNT_FRONTEND_ORIGIN = "http://127.0.0.1:5175"
RESULT_SHARING_ENABLED = False
DOCUMENT_OCR_BACKEND = "documents.ocr.placeholder_extract_text"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "eval-" + _eval_marker["run_id"]}}
# No real external messaging credentials may leak into the rehearsal.
WHATSAPP_ACCESS_TOKEN = ""
WHATSAPP_PHONE_NUMBER_ID = ""
WHATSAPP_RESULT_TEMPLATE = ""
WHATSAPP_APP_SECRET = ""

# Optional operator-supplied private forwarding origin, scoped to this run only.
_eval_origin = os.environ.get("EEE_EVALUATION_FRONTEND_ORIGIN")
if _eval_origin:
    from urllib.parse import urlsplit
    _eval_url = urlsplit(_eval_origin)
    if (_eval_url.scheme != "https" or not _eval_url.hostname or "*" in _eval_origin
            or _eval_url.username or _eval_url.password or _eval_url.query or _eval_url.fragment
            or _eval_url.path not in ("", "/")):
        raise RuntimeError("Use one exact HTTPS frontend origin without wildcard or credentials.")
    import re
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", _eval_url.hostname):
        raise RuntimeError("Use an exact DNS hostname for the forwarded origin.")
    _eval_url.port
    ALLOWED_HOSTS.append(_eval_url.hostname)
    CSRF_TRUSTED_ORIGINS.append(_eval_url.scheme + "://" + _eval_url.netloc)
    TEACHING_PORTAL_URL = _eval_url.scheme + "://" + _eval_url.netloc + "/portal"
    PASSWORD_RESET_FRONTEND_URL = _eval_url.scheme + "://" + _eval_url.netloc + "/reset-password"
    STUDENT_ACCOUNT_FRONTEND_ORIGIN = _eval_url.scheme + "://" + _eval_url.netloc
