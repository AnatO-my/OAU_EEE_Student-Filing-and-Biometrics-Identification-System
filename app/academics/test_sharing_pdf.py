import base64
import hashlib
import io
import uuid

import pdfplumber
from django.core import mail
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import ResultShareBatch
from .sharing import build_preview, digest, report_for
from .sharing_pdf import make_snapshot, render_statement, snapshot_bytes
from .sharing_worker import process_next
from .test_sharing import ResultSharingTests


@override_settings(RESULT_SHARING_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StatementDeliveryTests(APITestCase):
    setUp = ResultSharingTests.setUp
    enable = ResultSharingTests.enable
    preview = ResultSharingTests.preview
    queue = ResultSharingTests.queue

    def test_exact_reviewed_pdf_is_attached_once_and_kept_private(self):
        self.payload["channels"] = ["email"]
        data = self.preview().data
        public = data["preview"][0]["report"]["pdf"]
        self.assertNotIn("content_base64", public)
        response = self.client.get(public["url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(hashlib.sha256(response.content).hexdigest(), public["sha256"])
        self.assertEqual(self.queue(data).status_code, 202)
        process_next(channel="email")
        self.assertIsNone(process_next(channel="email"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.guardian.email])
        filename, content, mime = message.attachments[0]
        self.assertEqual(filename, public["filename"])
        self.assertEqual(mime, "application/pdf")
        self.assertEqual(content, response.content)
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        self.assertIn(self.student.full_name, text)
        self.assertIn("EEE301", text)
        self.assertIn("Calculated semester GPA", text)
        self.assertIn("not an official transcript", text)
        self.assertNotIn("FICTIONAL", text)
        self.assertNotIn("SAMPLE", text)

    def test_pdf_endpoint_requires_hod_and_batch_membership(self):
        data = self.preview().data
        url = data["preview"][0]["report"]["pdf"]["url"]
        self.assertEqual(self.client.get(reverse("result-share-pdf", kwargs={
            "batch_id": data["id"], "student_id": uuid.uuid4()})).status_code, 404)
        for user in (self.staff, None):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_legacy_batch_remains_plain_email(self):
        self.payload["channels"] = ["email"]
        data = self.preview().data
        batch = ResultShareBatch.objects.get(pk=data["id"])
        legacy, _ = build_preview([self.student], batch.academic_session, batch.semester,
                                  batch.channels, include_pdf=False)
        batch.preview, batch.history_digest = legacy, digest(legacy)
        batch.save(update_fields=["preview", "history_digest"])
        self.assertEqual(self.client.get(data["preview"][0]["report"]["pdf"]["url"]).status_code, 404)
        self.assertEqual(self.queue({"id": data["id"], "history_digest": batch.history_digest}).status_code, 202)
        process_next(channel="email")
        self.assertEqual(mail.outbox[0].attachments, [])
        self.assertIn("Semester GPA: 4", mail.outbox[0].body)

    def test_snapshot_bytes_and_fresh_preview_are_deterministic(self):
        report = report_for(self.student, self.offering.academic_session, "harmattan", include_pdf=True)
        again = report_for(self.student, self.offering.academic_session, "harmattan", include_pdf=True)
        self.assertEqual(report, again)
        snapshot = dict(report["pdf"])
        snapshot["content_base64"] = base64.b64encode(b"%PDF-tampered").decode()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            snapshot_bytes(snapshot)


class StatementLayoutTests(SimpleTestCase):
    def test_long_multi_page_results_repeat_headers_and_keep_all_rows(self):
        rows = [{"id": i, "course": f"TEST{i:03}", "title": "Long course title & laboratory <practice> " * 5,
                 "session": "2026/2027", "semester": "harmattan", "attempt": 1,
                 "score": "68", "units": 3, "grade_point": "4"} for i in range(70)]
        rows.append({**rows[0], "id": 99, "course": "EARLIER", "session": "2025/2026"})
        report = {"records": rows, "gpa": "4", "cgpa": "4"}
        content = render_statement(name="Synthetic Student", identifier="TEST/001", session="2026/2027",
            semester="harmattan", report=report)
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            self.assertGreater(len(pdf.pages), 2)
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            self.assertNotIn("EARLIER", text)
            for i in range(70):
                self.assertIn(f"TEST{i:03}", text)
            for number, page in enumerate(pdf.pages, 1):
                self.assertIn(f"Page {number}", page.extract_text())
                # Table content stays above the footer and within the page bounds.
                for word in page.extract_words():
                    self.assertGreaterEqual(word["x0"], 40)
                    self.assertLessEqual(word["x1"], page.width - 40)
                    self.assertLessEqual(word["bottom"], page.height - 20)
                if "TEST" in page.extract_text():
                    self.assertIn("Course / title", page.extract_text())

    def test_optional_titles_and_institution_are_omitted_safely(self):
        snapshot = make_snapshot(name="A & B", identifier="../../bad\r\nname", session="2026/2027",
            semester="harmattan", report={"records": [], "gpa": "0", "cgpa": "0"})
        self.assertNotIn("/", snapshot["filename"])
        self.assertNotIn("\n", snapshot["filename"])
        self.assertTrue(snapshot_bytes(snapshot).startswith(b"%PDF-"))
