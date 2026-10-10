import io
import json
import uuid
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient

from students.models import Guardian, Student
from . import test_api as fixtures
from .models import (AcademicSession, Course, CourseOffering, Result, ResultShareBatch,
                     ResultShareDelivery, GuardianSharingPreference)
from .sharing import set_preference
from .sharing_transport import RejectedSubmission, UncertainSubmission, submit_whatsapp
from .sharing_worker import process_next


@override_settings(RESULT_SHARING_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    WHATSAPP_ACCESS_TOKEN="synthetic-token", WHATSAPP_PHONE_NUMBER_ID="12345",
    WHATSAPP_API_VERSION="v99.0", WHATSAPP_RESULT_TEMPLATE="synthetic_report",
    WHATSAPP_TEMPLATE_LANGUAGE="en_US")
class ResultSharingTests(APITestCase):
    def setUp(self):
        fixtures.ResultCreateAPITests.setUp(self)
        Result.objects.create(student=self.student, offering=self.offering,
            score=Decimal("68"), credit_units=3, is_verified=True)
        self.guardian = Guardian.objects.create(student=self.student, full_name="Example Parent",
            relationship="Parent", phone_number="+2348000000000", email="parent@example.test")
        self.enable(self.guardian)
        self.client.force_authenticate(self.hod)
        self.payload = {"request_id": str(uuid.uuid4()), "student_ids": [str(self.student.pk)],
            "academic_session": self.offering.academic_session_id, "semester": "harmattan",
            "channels": ["email", "whatsapp"]}

    def enable(self, guardian):
        return set_preference(user=self.hod, guardian=guardian, email_enabled=True,
            whatsapp_enabled=True, evidence="Synthetic recipient authorization and WhatsApp opt-in.")

    def preview(self, payload=None):
        return self.client.post(reverse("result-share-preview"), payload or self.payload, format="json")

    def queue(self, data=None):
        data = data or self.preview().data
        return self.client.post(reverse("result-share-send", kwargs={"batch_id": data["id"]}),
            {"expected_digest": data["history_digest"]}, format="json")

    def test_preview_has_only_verified_selected_report_and_no_send(self):
        response = self.preview()
        self.assertEqual(response.status_code, 201)
        report = response.data["preview"][0]["report"]
        self.assertEqual(report["gpa"], "4")
        self.assertEqual(report["cgpa"], "4")
        self.assertIn("EEE301", report["text"])
        self.assertEqual(response.data["counts"], {"draft": 2})
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("no-store", response["Cache-Control"])

    def test_preview_idempotency_and_conflicting_request(self):
        first, second = self.preview(), self.preview()
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(ResultShareBatch.objects.count(), 1)
        self.assertEqual(ResultShareDelivery.objects.count(), 2)
        changed = {**self.payload, "channels": ["email"]}
        self.assertEqual(self.preview(changed).status_code, 400)

    def test_queue_repeat_click_does_not_resend(self):
        data = self.preview().data
        self.assertEqual(self.queue(data).status_code, 202)
        self.assertEqual(self.queue(data).status_code, 202)
        with patch("academics.sharing_worker.submit_whatsapp", return_value="synthetic-message"):
            process_next()
            process_next()
            self.assertIsNone(process_next())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.guardian.email])
        self.assertEqual(mail.outbox[0].bcc, [])
        self.assertEqual(self.queue(data).status_code, 202)
        self.assertIsNone(process_next())
        self.assertEqual(len(mail.outbox), 1)

    def test_non_hod_cannot_use_any_endpoint(self):
        data = self.preview().data
        for user in (self.staff, None):
            self.client.force_authenticate(user)
            self.assertEqual(self.preview().status_code, 403)
            self.assertEqual(self.queue(data).status_code, 403)
            self.assertEqual(self.client.get(reverse("result-share-detail",
                kwargs={"batch_id": data["id"]})).status_code, 403)
            self.assertEqual(self.client.post(reverse("result-share-retry",
                kwargs={"batch_id": data["id"]}), {}, format="json").status_code, 403)
            self.assertEqual(self.client.put(reverse("guardian-result-sharing", kwargs={
                "student_id": self.student.pk, "guardian_id": self.guardian.pk}),
                {"email_enabled": True, "whatsapp_enabled": True, "evidence": "x"}, format="json").status_code, 403)

    def test_missing_or_unverified_results_block_student(self):
        Result.objects.update(is_verified=False)
        response = self.preview()
        self.assertEqual(response.data["counts"], {"skipped": 2})
        self.assertIsNone(response.data["preview"][0]["report"])
        self.assertEqual(self.queue(response.data).status_code, 400)

    def test_unverified_previous_results_not_silently_omitted(self):
        old = AcademicSession.objects.create(name="2025/2026")
        offering = CourseOffering.objects.create(course=self.offering.course, academic_session=old,
            semester="rain", level=200, credit_units=3)
        Result.objects.create(student=self.student, offering=offering,
            score=Decimal("30"), credit_units=3, is_verified=False)
        self.assertIsNone(self.preview().data["preview"][0]["report"])

    def test_cgpa_counts_failed_attempts_and_excludes_future(self):
        Result.objects.create(student=self.student, offering=self.offering, attempt_number=2,
            score=Decimal("0"), credit_units=3, is_verified=True)
        future = CourseOffering.objects.create(course=self.offering.course,
            academic_session=self.offering.academic_session, semester="rain", level=300, credit_units=9)
        Result.objects.create(student=self.student, offering=future, score=None,
                              credit_units=9, is_verified=False)
        report = self.preview().data["preview"][0]["report"]
        self.assertEqual(report["cgpa"], "2")
        self.assertEqual(len(report["records"]), 2)

    def test_contact_and_permission_diagnostics(self):
        self.guardian.phone_number = "08000000000"
        self.guardian.email = ""
        self.guardian.save()
        response = self.preview()
        reasons = {r["diagnostic_code"] for r in response.data["preview"][0]["recipients"]}
        self.assertEqual(reasons, {"invalid_email", "international_phone_required"})

    def test_sharing_defaults_off_and_missing_guardians_visible(self):
        GuardianSharingPreference.objects.all().delete()
        response = self.preview()
        self.assertEqual(response.data["counts"], {"skipped": 2})
        other = Student.objects.create(identifier_type="utme", identifier_value="000999",
            full_name="No Guardians", phone_number="000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        data = self.preview({**self.payload, "request_id": str(uuid.uuid4()),
            "student_ids": [str(other.pk)]}).data
        self.assertEqual(data["preview"][0]["diagnostic_code"], "results_missing_or_unverified")
        self.assertEqual(data["preview"][0]["recipients"], [])

    def test_duplicate_guardian_contact_not_resent(self):
        duplicate = Guardian.objects.create(student=self.student, full_name="Same contact",
            relationship="Guardian", phone_number=self.guardian.phone_number, email=self.guardian.email)
        self.enable(duplicate)
        data = self.preview().data
        self.assertEqual(data["counts"], {"draft": 2, "skipped": 2})
        self.assertEqual(sum(r["diagnostic_code"] == "duplicate_contact"
            for r in data["preview"][0]["recipients"]), 2)

    def test_independent_student_reports_and_email_recipient_isolation(self):
        other = Student.objects.create(identifier_type="utme", identifier_value="00999",
            full_name="Other Student", phone_number="000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        Result.objects.create(student=other, offering=self.offering,
            score=Decimal("90"), credit_units=3, is_verified=True)
        guardian = Guardian.objects.create(student=other, full_name="Other Parent",
            relationship="Parent", phone_number="+2348000000001", email="other@example.test")
        self.enable(guardian)
        data = self.preview({**self.payload, "student_ids": [str(self.student.pk), str(other.pk)],
            "channels": ["email"]}).data
        self.assertEqual(self.queue(data).status_code, 202)
        process_next()
        process_next()
        self.assertEqual(len(mail.outbox), 2)
        messages = {m.to[0]: m.body for m in mail.outbox}
        self.assertNotIn("Other Student", messages[self.guardian.email])
        self.assertNotIn("Example Student", messages[guardian.email])

    def test_stale_preview_rejects_result_and_contact_changes(self):
        data = self.preview().data
        Result.objects.update(score=Decimal("70"))
        self.assertEqual(self.queue(data).status_code, 400)
        self.assertFalse(ResultShareDelivery.objects.filter(status="queued").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_revocation_after_queue_cancels_without_send(self):
        self.assertEqual(self.queue().status_code, 202)
        set_preference(user=self.hod, guardian=self.guardian, email_enabled=False,
            whatsapp_enabled=False, evidence="Recipient withdrew permission.")
        with patch("academics.sharing_worker.submit_whatsapp") as send:
            process_next()
            process_next()
            send.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(ResultShareDelivery.objects.filter(status="cancelled").count(), 2)

    def test_unconfigured_provider_prevents_queue(self):
        with override_settings(WHATSAPP_ACCESS_TOKEN=""):
            self.assertEqual(self.queue().status_code, 400)
        self.assertFalse(ResultShareDelivery.objects.filter(status="queued").exists())
        with override_settings(RESULT_SHARING_ENABLED=False):
            self.assertEqual(self.queue().status_code, 400)

    def test_known_rejection_retries_without_resending_accepted(self):
        data = self.preview().data
        self.queue(data)
        with patch("academics.sharing_worker.submit_whatsapp", side_effect=RejectedSubmission):
            process_next()
            process_next()
        failed = ResultShareDelivery.objects.get(status="failed")
        retry = reverse("result-share-retry", kwargs={"batch_id": data["id"]})
        self.assertEqual(self.client.post(retry).data["requeued"], 1)
        with patch("academics.sharing_worker.submit_whatsapp", return_value="accepted-id"):
            process_next()
        self.assertEqual(len(mail.outbox), 1)
        failed.refresh_from_db()
        self.assertEqual(failed.status, "accepted")
        self.assertEqual(failed.attempts, 2)

    def test_unknown_and_processing_are_never_automatically_retried(self):
        data = self.preview().data
        self.queue(data)
        with patch("academics.sharing_worker.submit_whatsapp", side_effect=UncertainSubmission):
            process_next()
            process_next()
        retry = reverse("result-share-retry", kwargs={"batch_id": data["id"]})
        self.assertEqual(self.client.post(retry).data["requeued"], 0)
        self.assertIsNone(process_next())
        ResultShareDelivery.objects.filter(status="unknown").update(status="processing")
        self.assertIsNone(process_next())

    def test_retry_limit(self):
        data = self.preview().data
        ResultShareDelivery.objects.filter(channel="whatsapp").update(status="failed", attempts=3)
        retry = reverse("result-share-retry", kwargs={"batch_id": data["id"]})
        self.assertEqual(self.client.post(retry).data["requeued"], 0)

    def test_preferences_record_evidence_and_parent_scope(self):
        url = reverse("guardian-result-sharing", kwargs={"student_id": self.student.pk,
                                                        "guardian_id": self.guardian.pk})
        self.assertEqual(self.client.put(url, {"email_enabled": True,
            "whatsapp_enabled": True, "evidence": ""}, format="json").status_code, 400)
        wrong = reverse("guardian-result-sharing", kwargs={"student_id": uuid.uuid4(),
                                                          "guardian_id": self.guardian.pk})
        self.assertEqual(self.client.get(wrong).status_code, 404)

    def test_csrf_required_for_hod_queue(self):
        self.hod.set_password("SyntheticStrongPassword2026!")
        self.hod.save()
        client = APIClient(enforce_csrf_checks=True)
        client.login(username=self.hod.username, password="SyntheticStrongPassword2026!")
        self.assertEqual(client.post(reverse("result-share-preview"), self.payload,
                                    format="json").status_code, 403)

    def test_worker_command_processes_only_queue(self):
        self.preview()
        call_command("process_result_shares", limit=1, stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 0)

    def test_whatsapp_adapter_template_and_acceptance(self):
        self.preview()
        delivery = ResultShareDelivery.objects.get(channel="whatsapp")
        response = io.BytesIO(json.dumps({"messages": [{"id": "synthetic-wa-id"}]}).encode())
        with patch("academics.sharing_transport.urlopen", return_value=response) as http:
            self.assertEqual(submit_whatsapp(delivery), "synthetic-wa-id")
            request = http.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(body["to"], self.guardian.phone_number[1:])
            self.assertEqual(body["template"]["components"][0]["parameters"][0]["text"], delivery.body)
            self.assertNotIn("\n", delivery.body)

    def test_whatsapp_adapter_error_classification(self):
        self.preview()
        delivery = ResultShareDelivery.objects.get(channel="whatsapp")
        for code, exception in ((400, RejectedSubmission), (429, RejectedSubmission), (500, UncertainSubmission)):
            with patch("academics.sharing_transport.urlopen", side_effect=HTTPError(
                    "https://example.test", code, "synthetic", {}, None)):
                with self.assertRaises(exception):
                    submit_whatsapp(delivery)


    def test_contact_change_before_queue_rejected(self):
        data = self.preview().data
        self.guardian.email = "changed@example.test"
        self.guardian.save()
        self.assertEqual(self.queue(data).status_code, 400)
        self.assertFalse(ResultShareDelivery.objects.filter(status="queued").exists())

    def test_result_edit_after_queue_cancels_submission(self):
        self.queue()
        Result.objects.update(score=Decimal("72"), is_verified=False)
        with patch("academics.sharing_worker.submit_whatsapp") as send:
            process_next()
            process_next()
            send.assert_not_called()
        self.assertEqual(ResultShareDelivery.objects.filter(status="cancelled").count(), 2)
        self.assertEqual(len(mail.outbox), 0)

    def test_whatsapp_long_report_split_into_tracked_parts_without_truncation(self):
        for i in range(15):
            course = Course.objects.create(code=f"EEE{i:03}", title="Long report course")
            offering = CourseOffering.objects.create(course=course,
                academic_session=self.offering.academic_session, semester="harmattan", level=300, credit_units=3)
            Result.objects.create(student=self.student, offering=offering, score=Decimal("60"),
                credit_units=3, is_verified=True)
        data = self.preview().data
        parts = list(ResultShareDelivery.objects.filter(channel="whatsapp").order_by("part_number"))
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(row.body) <= 1024 for row in parts))
        combined = " ".join(row.body for row in parts)
        for i in range(15):
            self.assertIn(f"EEE{i:03}", combined)
        self.assertIn("Cumulative CGPA", combined)
        self.assertEqual(self.queue(data).status_code, 202)
        with patch("academics.sharing_worker.submit_whatsapp", return_value="synthetic") as send:
            while process_next() is not None:
                pass
            self.assertEqual(send.call_count, len(parts))
        self.assertEqual(len(mail.outbox), 1)

    def test_console_backend_cannot_claim_email_delivery(self):
        data = self.preview({**self.payload, "channels": ["email"]}).data
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            self.assertEqual(self.queue(data).status_code, 400)

    def test_no_recorded_semester_results_is_diagnosed(self):
        payload = {**self.payload, "semester": "rain"}
        data = self.preview(payload).data
        self.assertEqual(data["preview"][0]["diagnostic_code"], "results_missing_or_unverified")
        self.assertEqual(self.queue(data).status_code, 400)

    def test_linked_student_cannot_preview_guardian_reports(self):
        from django.contrib.auth import get_user_model
        account = get_user_model().objects.create_user(username="student-account")
        self.student.user = account
        self.student.save()
        self.client.force_authenticate(account)
        self.assertEqual(self.preview().status_code, 403)

    def test_email_uncertain_delivery_not_retried(self):
        data = self.preview({**self.payload, "channels": ["email"]}).data
        self.queue(data)
        with patch("academics.sharing_transport.EmailMessage.send", side_effect=TimeoutError):
            process_next()
        delivery = ResultShareDelivery.objects.get()
        self.assertEqual(delivery.status, "unknown")
        retry = reverse("result-share-retry", kwargs={"batch_id": data["id"]})
        self.assertEqual(self.client.post(retry).data["requeued"], 0)


    def test_history_list_is_paginated_and_hod_only(self):
        data = self.preview().data
        response = self.client.get(reverse("result-share-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], data["id"])
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(reverse("result-share-list")).status_code, 403)

    def test_duplicate_selection_is_rejected_before_creating_batch(self):
        response = self.preview({**self.payload, "student_ids": [str(self.student.pk), str(self.student.pk)]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ResultShareBatch.objects.exists())


    def test_guardian_admin_cannot_relink_sharing_contact_to_another_student(self):
        from django.test import Client
        other = Student.objects.create(identifier_type="utme", identifier_value="another-id",
            full_name="Another student", phone_number="000", admission_year=2024,
            mode_of_admission="utme", current_level=300)
        client = Client()
        client.force_login(self.hod)
        response = client.post(reverse("admin:students_guardian_change", args=[self.guardian.pk]),
            {"student": str(other.pk), "full_name": self.guardian.full_name,
             "phone_number": self.guardian.phone_number, "relationship": self.guardian.relationship,
             "email": self.guardian.email, "address": "", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        self.guardian.refresh_from_db()
        self.assertEqual(self.guardian.student_id, self.student.pk)
