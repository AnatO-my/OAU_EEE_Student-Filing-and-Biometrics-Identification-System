"""Isolated SQLite checks for optional demo deployment infrastructure."""
from .test_settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "demo_hosting.apps.DemoHostingConfig"]  # noqa: F405
DEMO_FILE_MAX_BYTES = 3 * 1024 * 1024
DEMO_STORAGE_MAX_BYTES = 50 * 1024 * 1024
