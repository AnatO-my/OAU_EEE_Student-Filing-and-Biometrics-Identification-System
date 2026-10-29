import uuid
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.core.management.base import CommandError
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from attendance import tests as fixtures
from attendance.services import assign_staff, confirm_roster
from academics.models import Course, CourseOffering
from . import services
from .models import MessageReceipt, Notification, MaterialVersion


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TeachingTests(TestCase):
    setUpFixture = fixtures.AttendanceTests.setUp
    make_student = fixtures.AttendanceTests.make_student
    roster = fixtures.AttendanceTests.roster
    session = fixtures.AttendanceTests.session
    def setUp(self):
        self.setUpFixture()
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="teaching"))
        self.other.user_permissions.add(*Permission.objects.filter(content_type__app_label="teaching"))
        self.user.email = "student@example.invalid"
        self.user.save(update_fields=["email"])
        self.roster()
        self.audience = {"students": True, "student_ids": [str(self.student.pk)]}
    def publish(self, **changes):
        return services.publish(**{**dict(user=self.staff, event_id=uuid.uuid4(), subject="Private subject",
            body="Private message body", audience=self.audience), **changes})
    def test_message_reads_versions_withdrawal_and_link_only_notification(self):
        version = self.publish()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/teaching/messages/").status_code, 200)
        receipt = version.receipts.get()
        self.assertIsNone(receipt.read_at)
        item = Notification.objects.get(receipt=receipt)
        self.assertEqual(services.send_notification(item.pk), "sent")
        self.assertEqual(services.send_notification(item.pk), "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("Private", mail.outbox[0].body)
        receipt.refresh_from_db()
        self.assertIsNone(receipt.read_at)
        url = f"/api/teaching/messages/{version.message_id}/"
        opened = self.client.get(url)
        self.assertEqual(opened.data["body"], "Private message body")
        receipt.refresh_from_db()
        self.assertIsNotNone(receipt.read_at)
        revised = self.publish(message=version.message, expected_version=1, body="Updated body")
        self.assertIsNone(revised.receipts.get().read_at)
        self.assertIsNotNone(version.receipts.get().read_at)
        withdrawn = self.publish(message=version.message, expected_version=2, withdrawn=True)
        self.assertEqual(withdrawn.receipts.count(), 1)
        result = self.client.get(url)
        self.assertTrue(result.data["withdrawn"])
        self.assertEqual(result.data["body"], "")
        self.assertEqual(services.send_notification(Notification.objects.get(receipt=withdrawn.receipts.get()).pk), "sent")
        self.assertIn("withdrawn", mail.outbox[-1].body)
        self.assertEqual(services.send_notification(Notification.objects.get(receipt=revised.receipts.get()).pk), "skipped")
    def test_message_author_recipient_scope_and_snapshot_filters(self):
        version = self.publish(audience={"students": True, "offering_ids": [self.offering.pk]})
        self.assertEqual(version.receipts.get().recipient_id, self.user.pk)
        with self.assertRaises(PermissionDenied):
            services.open_message(user=self.other, message=version.message)
        with self.assertRaises(PermissionDenied):
            self.publish(user=self.other, message=version.message, expected_version=1)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/teaching/messages/{version.message_id}/history/").status_code, 404)
        own = self.client.get("/api/teaching/messages/")
        self.assertEqual(own.data, [])
    def test_publication_idempotency_and_ambiguous_mail_never_auto_retried(self):
        event = uuid.uuid4()
        first = self.publish(event_id=event)
        self.assertEqual(self.publish(event_id=event).pk, first.pk)
        with self.assertRaises(ValidationError):
            self.publish(event_id=event, body="Other body")
        item = Notification.objects.get(receipt=first.receipts.get())
        with patch("teaching.services.EmailMessage.send", return_value=0) as send:
            self.assertEqual(services.send_notification(item.pk), "unknown")
            self.assertEqual(services.send_notification(item.pk), "unknown")
            self.assertEqual(send.call_count, 1)
    def test_notification_skips_changed_email_or_removed_course_recipient(self):
        version = self.publish(audience={"students": True, "offering_ids": [self.offering.pk]})
        confirm_roster(user=self.hod, offering=self.offering, student_ids=[self.retaker.pk], expected_revision=1)
        self.assertEqual(services.send_notification(Notification.objects.get(receipt=version.receipts.get()).pk), "skipped")
    def material(self, **changes):
        return services.save_material(**{**dict(user=self.staff, offering=self.offering, event_id=uuid.uuid4(),
            title="Course notes", reason="Teaching resource", upload=SimpleUploadedFile("notes.pdf", b"%PDF-1.4 synthetic")), **changes})
    def test_material_replacement_withdrawal_retains_private_versions(self):
        from django.core.files.storage import FileSystemStorage
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as root:
            field = MaterialVersion._meta.get_field("file")
            with patch.object(field, "storage", FileSystemStorage(location=root)):
                first = self.material()
                self.client.force_authenticate(self.user)
                path = f"/api/teaching/materials/{first.material_id}/versions/1/download/"
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
                replacement = self.material(material=first.material, expected_version=1, upload=SimpleUploadedFile("new.pdf", b"%PDF-1.4 revised"))
                self.assertEqual(self.client.get(path).status_code, 403)
                self.client.force_authenticate(self.other)
                self.assertEqual(self.client.get(path).status_code, 403)
                self.client.force_authenticate(self.staff)
                archived = self.client.get(path)
                self.assertEqual(archived.status_code, 200)
                archived.close()
                self.material(material=first.material, expected_version=2, upload=None, withdrawn=True)
                self.assertEqual(first.material.versions.count(), 3)
                self.client.force_authenticate(self.user)
                self.assertEqual(self.client.get(f"/api/teaching/materials/{first.material_id}/versions/2/download/").status_code, 403)
    def test_timetable_student_overlap_warns_but_saves_and_scopes(self):
        other_course = Course.objects.create(code="EEE202", title="Other course")
        other = CourseOffering.objects.create(course=other_course, academic_session=self.year, semester="harmattan", level=200, credit_units=3)
        assign_staff(user=self.hod, offering=other, staff=self.staff, is_active=True)
        confirm_roster(user=self.hod, offering=other, student_ids=[self.student.pk], expected_revision=0)
        now = timezone.now()
        data = dict(user=self.staff, event_id=uuid.uuid4(), title="Lecture", venue="Room", starts_at=now,
            ends_at=now+timedelta(hours=1), active=True, reason="Class timetable")
        first = services.save_timetable(offering=self.offering, **data)
        second = services.save_timetable(offering=other, **{**data, "event_id": uuid.uuid4()})
        self.assertEqual(services.clashes(first), [second.pk])
        self.assertEqual(services.clashes(second), [first.pk])
        self.client.force_authenticate(self.user)
        rows = self.client.get("/api/teaching/timetable/")
        self.assertEqual(len(rows.data), 2)
        self.assertTrue(rows.data[0]["warning"])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/teaching/timetable/").data, [])
        with self.assertRaises(PermissionDenied):
            services.save_timetable(offering=self.offering, **{**data, "user": self.other, "event_id": uuid.uuid4()})

    def test_audience_directory_is_publish_scoped_minimal_metadata(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/teaching/audience-options/").status_code, 403)
        self.client.force_authenticate(self.staff)
        response = self.client.get("/api/teaching/audience-options/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response.data["students"][0]["identifier_value"], self.student.identifier_value)
        self.assertNotIn("email", response.data["students"][0])
        self.assertNotIn("phone_number", response.data["students"][0])

    def test_notification_rejects_unsafe_or_unconfigured_portal_base_before_sending(self):
        version = self.publish()
        item = Notification.objects.get(receipt=version.receipts.get())
        for origin in ("", "javascript:alert(1)", "https://example.invalid/portal?old=1", "https://example.invalid/portal#fragment", "https://user:password@example.invalid/portal"):
            with self.settings(TEACHING_PORTAL_URL=origin):
                with self.assertRaises(ValidationError):
                    services.send_notification(item.pk)
            item.refresh_from_db()
            self.assertEqual(item.state, "pending")


    def test_notification_command_sends_once_and_leaves_unknown_outcomes_alone(self):
        version = self.publish()
        item = Notification.objects.get(receipt=version.receipts.get())
        call_command("send_teaching_notifications", limit=1, stdout=io.StringIO())
        call_command("send_teaching_notifications", limit=1, stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 1)
        item.refresh_from_db()
        self.assertEqual(item.state, "sent")
        item.state = "unknown"
        item.save(update_fields=["state"])
        call_command("send_teaching_notifications", stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_notification_watch_honours_an_existing_stop_marker_without_sending(self):
        self.publish()
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "stop"
            marker.touch()
            call_command("send_teaching_notifications", watch=True, stop_file=str(marker), stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notification.objects.get().state, "pending")

    def test_notification_watch_finishes_current_email_then_stops(self):
        self.publish()
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "stop"
            def send_and_stop(pk):
                result = services.send_notification(pk)
                marker.touch()
                return result
            with patch("teaching.management.commands.send_teaching_notifications.send_notification", side_effect=send_and_stop):
                call_command("send_teaching_notifications", watch=True, interval=1, stop_file=str(marker), stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Notification.objects.get().state, "sent")

    def test_notification_command_rejects_invalid_options_before_processing(self):
        self.publish()
        for options in ({"limit": 0}, {"limit": 1001}, {"interval": float("nan")}, {"interval": 0}, {"stop_file": "synthetic-stop"}):
            with self.assertRaises(CommandError):
                call_command("send_teaching_notifications", stdout=io.StringIO(), **options)
        self.assertEqual(Notification.objects.get().state, "pending")

    def test_notification_command_does_not_mark_console_output_as_delivered(self):
        self.publish()
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            with self.assertRaises(CommandError):
                call_command("send_teaching_notifications", stdout=io.StringIO())
        self.assertEqual(Notification.objects.get().state, "pending")
