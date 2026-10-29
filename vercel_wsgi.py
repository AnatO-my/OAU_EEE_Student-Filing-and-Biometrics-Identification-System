"""Vercel entrypoint; never runs migrations, seeds accounts or starts workers."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.vercel_settings"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
