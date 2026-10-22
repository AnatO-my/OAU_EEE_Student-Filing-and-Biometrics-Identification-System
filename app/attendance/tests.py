import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AdviserAssignment
from students.models import Student
from students.services import students_visible_to
from academics.models import AcademicSession, Course, CourseOffering, Result, CurrentAcademicSession, AcademicSessionSelection
from academics.current_session import current_session_name, select_current_session
from .models import AttendanceRecord, AttendanceCorrection, AttendanceEvent, CourseStaffAssignment
from .services import (assign_staff, confirm_roster, roster_candidates, open_session,
                       close_session, record_manual, correct_record)


# Exercise roster approval, attendance workflows, permissions, and API behavior.
@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class AttendanceTests(TestCase):
    # Create the academic data, users, assigned staff, and test client.
    def setUp(self):
        User = get_user_model()
        self.hod = User.objects.create_superuser(username="attendance-hod", password="synthetic-password", email="hod@example.invalid")
        self.staff = User.objects.create_user(username="course-staff", is_staff=True)
        self.other = User.objects.create_user(username="other-staff", is_staff=True)
        self.user = User.objects.create_user(username="student-user")
        self.year = AcademicSession.objects.create(name="2026/2027")
        self.old_year = AcademicSession.objects.create(name="2025/2026")
        self.course = Course.objects.create(code="EEE201", title="Synthetic course")
        self.offering = CourseOffering.objects.create(course=self.course, academic_session=self.year,
            semester="harmattan", level=200, credit_units=3)
        self.old_offering = CourseOffering.objects.create(course=self.course, academic_session=self.old_year,
            semester="rain", level=200, credit_units=3)
        self.student = self.make_student("ATT-001", 200, self.user)
        self.retaker = self.make_student("ATT-002", 300)
        self.outsider = self.make_student("ATT-003", 400)
        for staff in (self.staff, self.other):
            staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="attendance"))
        assign_staff(user=self.hod, offering=self.offering, staff=self.staff, is_active=True)
        self.client = APIClient()

    # Build a student fixture with the requested level and optional login.
    def make_student(self, identifier, level, user=None):
        return Student.objects.create(identifier_type="matriculation", identifier_value=identifier,
            full_name=identifier, phone_number="+2340000000000", admission_year=2024,
            mode_of_admission="utme", current_level=level, user=user)

    # Confirm a roster through the service using the current revision.
    def roster(self, ids=None, revision=0, user=None):
        return confirm_roster(user=user or self.hod, offering=self.offering,
            student_ids=ids or [self.student.pk], expected_revision=revision)

    # Ensure a roster exists, then open a session with overridable times.
    def session(self, **kwargs):
        if not hasattr(self, "approved"):
            self.approved = self.roster()
        now = timezone.now()
        return open_session(user=kwargs.get("user", self.staff), offering=self.offering,
            title="Class one", starts_at=kwargs.get("start", now-timedelta(minutes=1)),
            ends_at=kwargs.get("end", now+timedelta(hours=1)))

    # Submit a manual attendance event with convenient test defaults.
    def mark(self, session, **kwargs):
        return record_manual(user=kwargs.get("user", self.staff), session=session,
            student=kwargs.get("student", self.student), event_id=kwargs.get("event_id", uuid.uuid4()),
            reason=kwargs.get("reason", "Manual check at class"))

    # Include level-matched students and retakers whose latest verified result failed.
    def test_candidates_include_level_and_verified_failed_retaker(self):
        Result.objects.create(student=self.retaker, offering=self.old_offering, score=Decimal("20"),
            credit_units=3, is_verified=True)
        candidates = {row["student_id"]: row["reasons"] for row in roster_candidates(self.offering)}
        self.assertEqual(candidates[str(self.student.pk)], ["current_level"])
        self.assertEqual(candidates[str(self.retaker.pk)], ["latest_verified_attempt_failed"])
        self.assertNotIn(str(self.outsider.pk), candidates)

    # A later passing attempt removes an earlier failed-attempt suggestion.
    def test_later_pass_removes_failed_suggestion(self):
        for attempt, score in [(1, "20"), (2, "60")]:
            Result.objects.create(student=self.retaker, offering=self.old_offering, attempt_number=attempt,
                score=Decimal(score), credit_units=3, is_verified=True)
        self.assertNotIn(str(self.retaker.pk), [row["student_id"] for row in roster_candidates(self.offering)])

    # Unverified failing results do not affect roster candidate suggestions.
    def test_unverified_failure_is_not_suggested(self):
        Result.objects.create(student=self.retaker, offering=self.old_offering, score=Decimal("20"),
            credit_units=3, is_verified=False)
        self.assertNotIn(str(self.retaker.pk), [row["student_id"] for row in roster_candidates(self.offering)])

    # Exclude students who are inactive or no longer undergraduates.
    def test_inactive_and_graduated_students_not_suggested(self):
        self.student.academic_status = "graduated"
        self.student.save()
        self.assertEqual(roster_candidates(self.offering), [])

    # Reject roster confirmation by staff without HOD authority.
    def test_only_hod_confirms_roster(self):
        with self.assertRaises(PermissionDenied): self.roster(user=self.staff)

    # Permit the HOD to explicitly include an eligible student from another level.
    def test_hod_can_include_retaker_outside_level(self):
        roster = self.roster([self.student.pk, self.retaker.pk])
        self.assertEqual(roster.students.count(), 2)

    # Reject duplicate, unknown, and inactive roster members.
    def test_roster_rejects_duplicate_unknown_and_inactive(self):
        for ids in ([self.student.pk, self.student.pk], [uuid.uuid4()]):
            with self.assertRaises(ValidationError): self.roster(ids)
        self.student.is_active = False
        self.student.save()
        with self.assertRaises(ValidationError): self.roster()

    # Require roster updates to use the latest confirmed revision.
    def test_stale_roster_revision_rejected(self):
        self.roster()
        with self.assertRaises(ValidationError): self.roster(revision=0)

    # Require HOD approval before assigned staff can open a session.
    def test_class_requires_hod_confirmed_roster(self):
        now = timezone.now()
        with self.assertRaises(ValidationError):
            open_session(user=self.staff, offering=self.offering, title="Unapproved",
                starts_at=now, ends_at=now+timedelta(hours=1))

    # Deny session creation when staff are not assigned to the offering.
    def test_unassigned_staff_cannot_open_class(self):
        with self.assertRaises(PermissionDenied): self.session(user=self.other)

    # Require the manage-attendance permission in addition to assignment.
    def test_assignment_without_action_permission_denied(self):
        self.staff.user_permissions.clear()
        with self.assertRaises(PermissionDenied): self.session()

    # Reject sessions whose end does not follow their start.
    def test_invalid_time_window_rejected(self):
        now = timezone.now()
        with self.assertRaises(ValidationError): self.session(start=now, end=now)

    # Keep the session's approved membership fixed despite later roster changes.
    def test_class_roster_snapshot_survives_later_changes(self):
        session = self.session()
        self.roster([self.retaker.pk], revision=1)
        self.student.current_level = 300
        self.student.save()
        self.mark(session)
        self.assertEqual(session.student_ids, [str(self.student.pk)])
        with self.assertRaises(ValidationError): self.mark(session, student=self.retaker)

    # Treat repeat check-ins as duplicate events without duplicating records.
    def test_repeat_events_create_one_record(self):
        session = self.session()
        first, _ = self.mark(session)
        second, _ = self.mark(session)
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceEvent.objects.count(), 2)

    # Replay an identical event successfully even after its session closes.
    def test_identical_retry_is_idempotent_even_after_closure(self):
        session = self.session()
        event_id = uuid.uuid4()
        self.mark(session, event_id=event_id)
        close_session(user=self.staff, session=session)
        _, replayed = self.mark(session, event_id=event_id)
        self.assertTrue(replayed)
        self.assertEqual(AttendanceEvent.objects.count(), 1)

    # Reject reuse of an idempotency key when its submitted data changes.
    def test_changed_event_replay_is_rejected(self):
        session = self.session()
        event_id = uuid.uuid4()
        self.mark(session, event_id=event_id)
        with self.assertRaises(ValidationError): self.mark(session, event_id=event_id, reason="Changed")

    # Prevent new check-ins for closed sessions and outside their time window.
    def test_closed_future_and_expired_sessions_reject_new_records(self):
        session = self.session()
        close_session(user=self.staff, session=session)
        with self.assertRaises(ValidationError): self.mark(session)
        now = timezone.now()
        for start, end in [(now+timedelta(hours=1), now+timedelta(hours=2)),
                           (now-timedelta(hours=2), now-timedelta(hours=1))]:
            with self.assertRaises(ValidationError): self.mark(self.session(start=start, end=end))

    # Enforce staff assignment revocation immediately for attendance writes.
    def test_revocation_denies_records(self):
        session = self.session()
        assign_staff(user=self.hod, offering=self.offering, staff=self.staff, is_active=False)
        with self.assertRaises(PermissionDenied): self.mark(session)

    # Require non-whitespace context for manually recorded attendance.
    def test_manual_reason_required(self):
        with self.assertRaises(ValidationError): self.mark(self.session(), reason=" ")

    # Preserve correction history and original event evidence after a status change.
    def test_correction_keeps_history_and_scan_evidence(self):
        session = self.session()
        self.mark(session)
        record = AttendanceRecord.objects.get()
        correct_record(user=self.staff, record=record, status="absent", reason="Original entry mistaken")
        correction = AttendanceCorrection.objects.get()
        self.assertEqual((correction.previous_status, correction.status), ("present", "absent"))
        self.assertEqual(AttendanceEvent.objects.count(), 1)
        self.assertTrue(self.mark(session)[0].duplicate)
        record.refresh_from_db()
        self.assertEqual(record.status, "absent")

    # Deny corrections by staff who are not assigned to the offering.
    def test_unassigned_correction_denied(self):
        self.mark(self.session())
        with self.assertRaises(PermissionDenied):
            correct_record(user=self.other, record=AttendanceRecord.objects.get(), status="absent", reason="Mistake")

    # Restrict session access and personal attendance results to the student.
    def test_student_cannot_record_or_view_another_student(self):
        session = self.session()
        self.mark(session)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(f"/api/attendance/sessions/{session.pk}/").status_code, 404)
        self.assertEqual(len(self.client.get("/api/me/attendance/").data["results"]), 1)
        other_user = get_user_model().objects.create_user(username="other-student")
        self.outsider.user = other_user
        self.outsider.save()
        self.client.force_authenticate(other_user)
        self.assertEqual(self.client.get("/api/me/attendance/").data["count"], 0)
        self.assertEqual(self.client.put(f"/api/attendance/offerings/{self.offering.pk}/roster/", {}).status_code, 403)

    # Enforce CSRF checks on browser-authenticated manual attendance submissions.
    def test_api_manual_submission_and_csrf(self):
        session = self.session()
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(f"/api/attendance/sessions/{session.pk}/records/",
            {"student": str(self.student.pk), "event_id": str(uuid.uuid4()), "reason": "Manual"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    # Apply the database-selected academic session to attendance and adviser scope.
    def test_database_session_overrides_environment_and_changes_adviser_scope(self):
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label="students", codename="view_student"))
        AdviserAssignment.objects.create(staff=self.staff, academic_session=self.year.name, level=200)
        self.assertTrue(students_visible_to(self.staff, current_session_name()).exists())
        self.session()
        select_current_session(user=self.hod, academic_session=self.old_year, expected_session_id=None)
        self.assertEqual(current_session_name(), self.old_year.name)
        self.assertFalse(students_visible_to(self.staff, current_session_name()).exists())
        self.assertEqual(AcademicSessionSelection.objects.count(), 1)
        with self.assertRaises(PermissionDenied): self.session()

    # Restrict session selection to HODs and reject stale expected selections.
    def test_current_session_hod_only_and_stale_selection(self):
        with self.assertRaises(PermissionDenied):
            select_current_session(user=self.staff, academic_session=self.year, expected_session_id=None)
        select_current_session(user=self.hod, academic_session=self.year, expected_session_id=None)
        with self.assertRaises(ValidationError):
            select_current_session(user=self.hod, academic_session=self.old_year, expected_session_id=None)
        select_current_session(user=self.hod, academic_session=self.year, expected_session_id=self.year.pk)
        self.assertEqual(AcademicSessionSelection.objects.count(), 1)

    # Verify current-session API access and HOD-only update authorization.
    def test_current_session_api(self):
        self.client.force_authenticate(self.hod)
        response = self.client.put("/api/academic-sessions/current/",
            {"academic_session": self.year.pk, "expected_session_id": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "database")
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get("/api/academic-sessions/current/").status_code, 403)

    # Exercise roster approval, session creation, check-in, listing, and closure.
    def test_api_approved_roster_class_record_and_close(self):
        self.client.force_authenticate(self.hod)
        roster = self.client.put(f"/api/attendance/offerings/{self.offering.pk}/roster/",
            {"student_ids": [str(self.student.pk)], "expected_revision": 0}, format="json")
        self.assertEqual(roster.status_code, 200)
        self.client.force_authenticate(self.staff)
        now = timezone.now()
        opened = self.client.post("/api/attendance/sessions/", {"offering": self.offering.pk,
            "title": "API class", "starts_at": (now-timedelta(minutes=1)).isoformat(),
            "ends_at": (now+timedelta(hours=1)).isoformat()}, format="json")
        self.assertEqual(opened.status_code, 201)
        sid = opened.data["id"]
        recorded = self.client.post(f"/api/attendance/sessions/{sid}/records/",
            {"student": str(self.student.pk), "event_id": str(uuid.uuid4()), "reason": "Roll call"}, format="json")
        self.assertEqual(recorded.status_code, 201)
        rows = self.client.get(f"/api/attendance/sessions/{sid}/records/")
        self.assertEqual(rows.data["count"], 1)
        closed = self.client.post(f"/api/attendance/sessions/{sid}/close/", {}, format="json")
        self.assertEqual(closed.data["status"], "closed")

    # Prevent an event ID from being reused in a different session.
    def test_event_id_cannot_be_reused_for_another_class(self):
        event_id = uuid.uuid4()
        self.mark(self.session(), event_id=event_id)
        with self.assertRaises(ValidationError): self.mark(self.session(), event_id=event_id)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    # Verify the HOD admin action updates the selected academic session.
    def test_hod_admin_can_select_current_session(self):
        from django.test import Client
        client = Client()
        client.force_login(self.hod)
        response = client.post("/admin/academics/academicsession/", {
            "action": "make_current", "_selected_action": [str(self.year.pk)], "index": "0"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(current_session_name(), self.year.name)
        self.assertEqual(CurrentAcademicSession.objects.get(pk=1).academic_session_id, self.year.pk)

    # Retain each prior roster membership as an approval revision.
    def test_roster_confirmation_preserves_previous_membership(self):
        from .models import CourseRosterApproval
        self.roster()
        self.roster([self.retaker.pk], revision=1)
        first = CourseRosterApproval.objects.get(revision=1)
        self.assertEqual(first.student_ids, [str(self.student.pk)])
        self.assertEqual(CourseRosterApproval.objects.count(), 2)
