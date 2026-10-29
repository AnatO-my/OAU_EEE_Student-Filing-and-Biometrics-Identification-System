import os
import runpy
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.cache.backends.db import DatabaseCache
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.db import transaction
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from documents.models import private_storage
from .email_backend import DisabledEmailBackend
from .middleware import DemoRequestLimits
from .models import StorageBudget, StoredFile
from .storage import DemoDatabaseStorage


class StorageTests(TestCase):
    def test_files_survive_new_storage_instances_and_never_have_public_urls(self):
        storage = DemoDatabaseStorage()
        name = storage.save("documents/synthetic.pdf", ContentFile(b"%PDF-synthetic"))
        other = DemoDatabaseStorage()
        self.assertEqual(other.open(name).read(), b"%PDF-synthetic")
        self.assertEqual(other.size(name), 14)
        self.assertTrue(other.exists(name))
        with self.assertRaises(NotImplementedError):
            other.url(name)
        with self.assertRaises(NotImplementedError):
            other.path(name)
        other.delete(name)
        other.delete(name)
        self.assertEqual(StorageBudget.objects.get(pk=1).used_bytes, 0)
        with self.assertRaises(FileNotFoundError):
            storage.open(name)

    def test_existing_names_are_not_overwritten(self):
        storage = DemoDatabaseStorage()
        first = storage.save("synthetic.txt", ContentFile(b"original"))
        second = storage.save(first, ContentFile(b"replacement"))
        self.assertNotEqual(first, second)
        self.assertEqual(storage.open(first).read(), b"original")

    def test_application_rollback_removes_file_and_quota_changes(self):
        storage = DemoDatabaseStorage()
        with self.assertRaises(ValueError):
            with transaction.atomic():
                storage.save("synthetic.txt", ContentFile(b"synthetic"))
                raise ValueError("rollback the application write")
        self.assertFalse(StoredFile.objects.exists())
        self.assertFalse(StorageBudget.objects.exists())

    @override_settings(DEMO_FILE_MAX_BYTES=8, DEMO_STORAGE_MAX_BYTES=10)
    def test_per_file_limit_and_total_quota_leave_no_partial_records(self):
        storage = DemoDatabaseStorage()
        for data in (b"", b"123456789"):
            with self.assertRaises(ValidationError):
                storage.save("file.txt", ContentFile(data))
        first = storage.save("file.txt", ContentFile(b"12345678"))
        with self.assertRaises(ValidationError):
            storage.save("more.txt", ContentFile(b"123"))
        self.assertEqual(StoredFile.objects.count(), 1)
        self.assertEqual(StorageBudget.objects.get(pk=1).used_bytes, 8)
        storage.delete(first)
        storage.save("more.txt", ContentFile(b"123"))

    def test_unsafe_names_and_write_modes_are_rejected(self):
        storage = DemoDatabaseStorage()
        for name in ("../private", "/private", "a\\b", "a\x00b"):
            with self.assertRaises(SuspiciousFileOperation):
                storage.exists(name)
        with self.assertRaises(ValueError):
            storage.open("file", "wb")

    def test_backend_choice_preserves_local_disk_default(self):
        self.assertIsInstance(private_storage(), FileSystemStorage)
        with override_settings(PRIVATE_STORAGE_BACKEND="demo_hosting.storage.DemoDatabaseStorage"):
            self.assertIsInstance(private_storage(), DemoDatabaseStorage)

    def test_login_counters_are_shared_between_cache_instances(self):
        first = DatabaseCache("eee_demo_cache", {})
        second = DatabaseCache("eee_demo_cache", {})
        first.set("synthetic-login", (5, 12345), 60)
        self.assertEqual(second.get("synthetic-login"), (5, 12345))
        second.delete("synthetic-login")
        self.assertIsNone(first.get("synthetic-login"))


class RequestAndEmailTests(SimpleTestCase):
    def test_oversized_requests_fail_before_application_code(self):
        middleware = DemoRequestLimits(lambda request: HttpResponse("ok"))
        request = RequestFactory().get("/api/")
        for length in ("5000000", "-1", "invalid"):
            request.META["CONTENT_LENGTH"] = length
            response = middleware(request)
            self.assertEqual(response.status_code, 413)
            self.assertIn("no-store", response["Cache-Control"])
        request.META["CONTENT_LENGTH"] = "100"
        self.assertEqual(middleware(request).status_code, 200)

    def test_disabled_email_never_reports_delivery_success(self):
        self.assertEqual(DisabledEmailBackend().send_messages([]), 0)
        with self.assertRaises(OSError):
            DisabledEmailBackend().send_messages([object()])


class VercelSettingsTests(SimpleTestCase):
    def load(self, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "synthetic-ca.pem"
            certificate.write_text("synthetic path fixture", encoding="utf-8")
            environment = {
                "DEMO_SYNTHETIC_ONLY": "true",
                "DEMO_PUBLIC_ORIGIN": "https://demo.example.invalid",
                "POSTGRES_HOST": "synthetic.aivencloud.com",
                "POSTGRES_DB": "eee_demo_synthetic",
                "POSTGRES_USER": "synthetic_demo_user",
                "POSTGRES_PASSWORD": "synthetic-not-a-real-password",
                "POSTGRES_SSLROOTCERT": str(certificate),
                "DJANGO_ALLOWED_HOSTS": "demo.example.invalid",
                "DJANGO_SECRET_KEY": "synthetic-key-for-isolated-configuration-checks-0123456789abcdef",
            }
            with patch.dict(os.environ, {**environment, **overrides}, clear=True), patch.dict(sys.modules):
                for module in ("config.settings", "config.postgres_settings", "config.production_settings"):
                    sys.modules.pop(module, None)
                return runpy.run_module("config.vercel_settings")

    def test_default_demo_has_shared_state_and_disables_email(self):
        config = self.load(VERCEL_URL="synthetic-123.vercel.app")
        self.assertFalse(config["DEBUG"])
        self.assertFalse(config["RESULT_SHARING_ENABLED"])
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertEqual(config["DATABASES"]["default"]["OPTIONS"]["sslmode"], "verify-full")
        self.assertEqual(config["CACHES"]["default"]["LOCATION"], "eee_demo_cache")
        self.assertIn("https://synthetic-123.vercel.app", config["CSRF_TRUSTED_ORIGINS"])
        self.assertEqual(config["EMAIL_BACKEND"], "demo_hosting.email_backend.DisabledEmailBackend")

    def test_refuses_integration_database_missing_ca_and_unsafe_origins(self):
        for overrides in (
            {"DEMO_SYNTHETIC_ONLY": "false"}, {"POSTGRES_DB": "defaultdb"},
            {"POSTGRES_PASSWORD": ""}, {"POSTGRES_SSLMODE": "require"},
            {"POSTGRES_SSLROOTCERT": "nonexistent-certificate.pem"}, {"AIVEN_CA_PEM": "invalid"},
            {"DEMO_PUBLIC_ORIGIN": "http://demo.example.invalid"},
            {"DEMO_PUBLIC_ORIGIN": "https://user:password@demo.example.invalid"},
            {"DEMO_PUBLIC_ORIGIN": "https://demo.example.invalid/path"},
            {"VERCEL_URL": "evil.invalid/path.vercel.app"},
        ):
            with self.subTest(overrides=list(overrides)), self.assertRaises(ImproperlyConfigured):
                self.load(**overrides)
