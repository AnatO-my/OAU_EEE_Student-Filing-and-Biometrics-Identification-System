import io
import uuid
import pdfplumber
from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase
from .test_sharing import ResultSharingTests
from .sharing_worker import process_next

@override_settings(RESULT_SHARING_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RevisedResultTests(APITestCase):
    setUp = ResultSharingTests.setUp
    enable = ResultSharingTests.enable
    preview = ResultSharingTests.preview
    queue = ResultSharingTests.queue

    def test_revision_label_snapshot_and_internal_reason_isolation(self):
        self.payload.update(channels=['email'], is_revised=True, revision_reason='INTERNAL-ONLY corrected entry')
        response = self.preview()
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        pdf = self.client.get(data['preview'][0]['report']['pdf']['url']).content
        with pdfplumber.open(io.BytesIO(pdf)) as document:
            text = ' '.join((p.extract_text() or '' for p in document.pages))
        self.assertIn('Revised Result', text)
        self.assertNotIn('INTERNAL-ONLY', text)
        self.assertEqual(self.queue(data).status_code, 202)
        process_next(channel='email')
        self.assertEqual(mail.outbox[-1].attachments[0][1], pdf)
        self.assertNotIn('INTERNAL-ONLY', mail.outbox[-1].body)

    def test_revision_reason_required(self):
        self.payload.update(is_revised=True)
        self.assertEqual(self.preview().status_code, 400)
