"""Loopback HTTP tests with actual authentication, cookies and byte streams."""
import hashlib
import http.client
from http.cookiejar import CookieJar
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from unittest import skipUnless
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request
from unittest.mock import patch

from django.test import LiveServerTestCase, override_settings
from django.conf import settings
from django.db import connection

from .models import AttendanceEvent, AttendanceRecord, PendingBatchImport, PendingCaptureBatch, PendingCaptureEvent
from .test_pending_batches import PendingBatchFixtureMixin
from .services import assign_staff


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027", SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class PendingBatchHTTPTests(PendingBatchFixtureMixin, LiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.password = "Synthetic-HTTP-Test-2026"
        self.staff.set_password(self.password)
        self.staff.save(update_fields=["password"])
        self.cookies = CookieJar()
        self.browser = build_opener(HTTPCookieProcessor(self.cookies))
        self.token = None

    def request(self, method, path, *, data=None, csrf=True, digest=None, extra_headers=None):
        headers = {"Content-Type": "application/x-ndjson" if isinstance(data, bytes) else "application/json"}
        if csrf and self.token:
            headers["X-CSRFToken"] = self.token
        if digest is not None:
            headers["X-Capture-SHA256"] = digest
        headers.update(extra_headers or {})
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        request = Request(getattr(self, "application_url", self.live_server_url) + path, data=data, headers=headers, method=method)
        try:
            response = self.browser.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, json.loads(body) if body else None, response.headers

    def login(self):
        status, payload, _ = self.request("GET", "/api/auth/csrf/")
        self.assertEqual(status, 200)
        self.token = payload["csrfToken"]
        status, _, _ = self.request("POST", "/api/auth/login/", data={"username": self.staff.username, "password": self.password})
        self.assertEqual(status, 200)
        # Login rotates the CSRF secret. Fetch the current token as a real client does.
        status, payload, _ = self.request("GET", "/api/auth/csrf/")
        self.assertEqual(status, 200)
        self.token = payload["csrfToken"]

    def raw_connection(self, data):
        request = Request(self.live_server_url + self.url)
        self.cookies.add_cookie_header(request)
        parsed = urlsplit(self.live_server_url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=10)
        conn.putrequest("POST", self.url)
        headers = {"Content-Type": "application/x-ndjson", "Content-Length": str(len(data)),
                   "X-CSRFToken": self.token, "X-Capture-SHA256": hashlib.sha256(data).hexdigest(),
                   "Cookie": request.get_header("Cookie", "")}
        for key, value in headers.items():
            conn.putheader(key, value)
        conn.endheaders()
        return conn

    def assert_pending_only(self):
        self.assertEqual(AttendanceRecord.objects.count(), 0)
        self.assertEqual(AttendanceEvent.objects.count(), 0)

    def test_authenticated_preview_import_list_preserve_exact_file_and_hide_probe(self):
        data = self.data()
        self.login()
        status, preview, _ = self.request("POST", self.url + "preview/", data=data)
        self.assertEqual(status, 200)
        self.assertEqual(preview["file_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)
        status, receipt, headers = self.request("POST", self.url, data=data, digest=preview["file_sha256"])
        self.assertEqual(status, 201)
        self.assertIn("no-store", headers["Cache-Control"])
        status, listing, _ = self.request("GET", self.url)
        self.assertEqual((status, listing["count"]), (200, 1))
        self.assertEqual(bytes(PendingCaptureEvent.objects.get().probe), b"synthetic-probe-only")
        for payload in (preview, receipt, listing):
            self.assertNotIn(self.events[0]["probe_base64"], json.dumps(payload))
        self.assert_pending_only()

    def test_missing_csrf_and_anonymous_uploads_create_no_evidence(self):
        data = self.data()
        status, _, _ = self.request("POST", self.url + "preview/", data=data)
        self.assertEqual(status, 403)
        self.login()
        for path in (self.url, self.url + "preview/"):
            status, _, _ = self.request("POST", path, data=data, csrf=False, digest=hashlib.sha256(data).hexdigest())
            self.assertEqual(status, 403)
            status, _, _ = self.request("POST", path, data=data, extra_headers={"X-CSRFToken": "x"*64})
            self.assertEqual(status, 403)
            status, _, _ = self.request("POST", path, data=data, extra_headers={"Origin": "https://untrusted.example.invalid"})
            self.assertEqual(status, 403)
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)

    def test_real_session_course_authorization_precedes_raw_stream_read(self):
        self.login()
        assign_staff(user=self.hod, offering=self.offering, staff=self.staff, is_active=False)
        with patch("attendance.pending_views.read_batch_stream") as read:
            status, _, _ = self.request("POST", self.url + "preview/", data=b"unread-synthetic-data")
            self.assertEqual(status, 404)
            read.assert_not_called()

    def test_utf8_content_type_parameter_preserves_file_bytes(self):
        self.login()
        data = self.data()
        status, receipt, _ = self.request("POST", self.url, data=data, digest=hashlib.sha256(data).hexdigest(),
                                         extra_headers={"Content-Type": "application/x-ndjson; charset=utf-8"})
        self.assertEqual(status, 201)
        self.assertEqual(receipt["file_sha256"], hashlib.sha256(data).hexdigest())

    def test_incomplete_http_upload_is_atomic_and_complete_retry_succeeds(self):
        data = self.data()
        self.login()
        conn = self.raw_connection(data)
        try:
            conn.send(data[:len(data)//2])
            conn.sock.shutdown(socket.SHUT_WR)
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
        finally:
            conn.close()
        self.assertEqual(PendingCaptureBatch.objects.count(), 0)
        self.assertEqual(PendingCaptureEvent.objects.count(), 0)
        self.assertEqual(PendingBatchImport.objects.count(), 0)
        status, _, _ = self.request("POST", self.url, data=data, digest=hashlib.sha256(data).hexdigest())
        self.assertEqual(status, 201)
        self.assert_pending_only()

    @contextmanager
    def application_process(self):
        """Fresh app process against the already isolated PostgreSQL test DB."""
        db = connection.settings_dict
        if not db["NAME"].startswith("test_"):
            raise AssertionError("Refusing to start a server against a non-test database.")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        workspace = Path(__file__).resolve().parents[2]
        env = {**os.environ, "POSTGRES_HOST": db["HOST"], "POSTGRES_PORT": str(db["PORT"]),
               "POSTGRES_DB": db["NAME"], "POSTGRES_USER": db["USER"], "POSTGRES_PASSWORD": db["PASSWORD"],
               "DJANGO_SECRET_KEY": settings.SECRET_KEY, "DJANGO_DEBUG": "true",
               "CURRENT_ACADEMIC_SESSION": "2026/2027"}
        self.application_url = f"http://127.0.0.1:{port}"
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen([sys.executable, str(workspace / "manage.py"), "runserver",
                f"127.0.0.1:{port}", "--noreload", "--nothreading", "--settings=config.ci_settings"],
                cwd=workspace, env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL, **flags)
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError("Synthetic application process exited before becoming ready.")
                    try:
                        status, _, _ = self.request("GET", "/api/auth/csrf/")
                        if status == 200:
                            break
                    except (URLError, ConnectionError, TimeoutError):
                        time.sleep(0.05)
                else:
                    raise AssertionError("Synthetic application server did not become ready.")
                yield
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                del self.application_url

    @skipUnless(connection.vendor == "postgresql", "Fresh processes require the isolated PostgreSQL test database.")
    def test_receipt_and_login_survive_application_process_restart(self):
        data = self.data()
        digest = hashlib.sha256(data).hexdigest()
        with self.application_process():
            self.login()
            status, preview, _ = self.request("POST", self.url + "preview/", data=data)
            self.assertEqual((status, preview["file_sha256"]), (200, digest))
            status, original, _ = self.request("POST", self.url, data=data, digest=digest)
            self.assertEqual(status, 201)
        # The old process is gone. A new process must use database evidence and
        # the existing authenticated cookie, without repeating login or capture.
        with self.application_process():
            status, retry, _ = self.request("POST", self.url, data=data, digest=digest)
            self.assertEqual(status, 200)
            self.assertEqual(retry["receipt_id"], original["receipt_id"])
            self.assertTrue(retry["replayed"])
            status, listing, _ = self.request("GET", self.url)
            self.assertEqual((status, listing["count"]), (200, 1))
        self.assertEqual((PendingCaptureEvent.objects.count(), PendingBatchImport.objects.count()), (1, 1))
        self.assert_pending_only()

    def test_unread_success_response_is_recovered_by_exact_http_retry(self):
        data = self.data()
        self.login()
        conn = self.raw_connection(data)
        try:
            conn.send(data)
            # Headers arrive after commit. Discard the receipt response body,
            # so the client must recover its unknown receipt through a retry.
            response = conn.getresponse()
            self.assertEqual(response.status, 201)
        finally:
            conn.close()
        original = PendingBatchImport.objects.get()
        status, retry, _ = self.request("POST", self.url, data=data, digest=hashlib.sha256(data).hexdigest())
        self.assertEqual(status, 200)
        self.assertTrue(retry["replayed"])
        self.assertEqual(retry["receipt_id"], str(original.pk))
        self.assertEqual((PendingCaptureEvent.objects.count(), PendingBatchImport.objects.count()), (1, 1))
        self.assert_pending_only()
