"""Synthetic reconciliation tests, no scanner or live database."""
import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from . import tests as fixtures
from .test_pending_batches import header, event, pack
from .pending_services import import_pending_batch, preview_pending_batch
from .models import PendingCaptureEvent, AttendanceRecord
from .reconciliation import register_reference, open_review, resolve_capture, course_rates


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class ReconciliationTests(TestCase):
    setUp = fixtures.AttendanceTests.setUp
    make_student = fixtures.AttendanceTests.make_student
    roster = fixtures.AttendanceTests.roster
    session = fixtures.AttendanceTests.session
    def capture(self, session):
        data = pack(header(session.pk), [event()])
        preview = preview_pending_batch(user=self.staff, session=session, data=data)
        import_pending_batch(user=self.staff, session=session, data=data, expected_sha256=preview["file_sha256"])
        return PendingCaptureEvent.objects.get(batch_id=preview["batch_id"])

    def test_deferred_archive_explicit_resolution_replay_and_rates(self):
        session = self.session()
        capture = self.capture(session)
        review = open_review(user=self.staff, capture=capture, mode="deferred")
        self.assertEqual(review.state, "archived")
        from .services import close_session
        close_session(user=self.staff, session=session)
        before = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((before["rate_percent"], before["pending_meetings"]), (None, 1))
        kwargs = dict(user=self.staff, capture=capture, student=self.student,
                      reason="Staff verified identity and meeting evidence", timing_confirmed=True)
        first = resolve_capture(**kwargs)
        self.assertEqual(resolve_capture(**kwargs).pk, first.pk)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 1)
        after = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((after["rate_percent"], after["pending_meetings"]), ("100.00", 0))
        self.assertTrue(PendingCaptureEvent.objects.filter(pk=capture.pk).exists())

    def test_live_unmatched_flagged_identity_and_timing_restrictions(self):
        session = self.session()
        capture = self.capture(session)
        self.assertEqual(open_review(user=self.staff, capture=capture, mode="live").state, "flagged")
        kwargs = dict(user=self.staff, capture=capture, student=self.student, reason="Evidence", timing_confirmed=True)
        for changes in ({"student": self.outsider}, {"timing_confirmed": False}, {"reason": " "}):
            with self.assertRaises(ValidationError):
                resolve_capture(**{**kwargs, **changes})
        with self.assertRaises(PermissionDenied):
            resolve_capture(**{**kwargs, "user": self.other})
        resolve_capture(**kwargs)
        with self.assertRaises(ValidationError):
            resolve_capture(**{**kwargs, "reason": "Changed claim"})

    def test_scanner_mapping_is_stable_and_not_hardware_enrolment(self):
        session = self.session()
        kwargs = dict(user=self.staff, session=session, student=self.student,
                      scanner_uuid=uuid.uuid4(), reference_id="12")
        first = register_reference(**kwargs)
        self.assertEqual(register_reference(**kwargs).pk, first.pk)
        with self.assertRaises(ValidationError):
            register_reference(**{**kwargs, "student": self.outsider})
        with self.assertRaises(PermissionDenied):
            register_reference(**{**kwargs, "user": self.other})

    def test_multiple_captures_count_once_and_queue_never_exposes_probes(self):
        session = self.session()
        for _ in range(2):
            capture = self.capture(session)
            open_review(user=self.staff, capture=capture, mode="deferred")
            resolve_capture(user=self.staff, capture=capture, student=self.student,
                            reason="Verified meeting identity", timing_confirmed=True)
        self.assertEqual(AttendanceRecord.objects.filter(session=session, student=self.student).count(), 1)
        self.client.force_authenticate(self.staff)
        response = self.client.get(f"/api/attendance/sessions/{session.pk}/captures/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("synthetic-probe", str(response.data))
        self.assertEqual(len(response.data["results"]), 2)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/attendance/sessions/{session.pk}/captures/").status_code, 404)


    def test_queue_untouched_archive_and_api_resolution(self):
        session = self.session()
        capture = self.capture(session)
        self.client.force_authenticate(self.staff)
        queue = self.client.get(f"/api/attendance/sessions/{session.pk}/captures/")
        self.assertEqual(queue.data["results"][0]["state"], "archived")
        url = f"/api/attendance/captures/{capture.pk}/resolve/"
        payload = {"student": str(self.student.pk), "reason": "Identity and timing reviewed", "timing_confirmed": True}
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        opened = self.client.post(f"/api/attendance/captures/{capture.pk}/review/", {"mode": "deferred"}, format="json")
        self.assertEqual(opened.status_code, 200)
        result = self.client.post(url, payload, format="json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["state"], "resolved")
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 404)

    def test_rates_closed_meetings_only_and_denominator_excludes_unknowns(self):
        first = self.session()
        self.mark = fixtures.AttendanceTests.mark.__get__(self)
        self.mark(first)
        from .services import close_session
        close_session(user=self.staff, session=first)
        second = self.session()
        close_session(user=self.staff, session=second)
        self.session()  # Open meetings do not count yet.
        rates = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rates["meetings_attended"], rates["eligible_recorded_meetings"], rates["rate_percent"]), (1, 2, "50.00"))
        self.capture(second)
        rates = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rates["pending_meetings"], rates["rate_percent"]), (1, "100.00"))
        self.client.force_authenticate(self.staff)
        response = self.client.get(f"/api/attendance/offerings/{self.offering.pk}/rates/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/attendance/offerings/{self.offering.pk}/rates/").status_code, 403)

    def test_reference_conflict_between_approved_students_and_inactive_staff(self):
        self.approved = self.roster(ids=[self.student.pk, self.retaker.pk])
        session = self.session()
        kwargs = dict(user=self.staff, session=session, student=self.student,
                      scanner_uuid=uuid.uuid4(), reference_id="slot-1")
        register_reference(**kwargs)
        with self.assertRaises(ValidationError):
            register_reference(**{**kwargs, "student": self.retaker})
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            register_reference(**kwargs)

    def test_empty_or_interrupted_import_cannot_create_absences(self):
        from .services import close_session
        for interrupted in (False, True):
            session = self.session()
            metadata = header(session.pk)
            metadata["interrupted_write_pending"] = interrupted
            data = pack(metadata, [event()] if interrupted else [])
            preview = preview_pending_batch(user=self.staff, session=session, data=data)
            import_pending_batch(user=self.staff, session=session, data=data, expected_sha256=preview["file_sha256"])
            if interrupted:
                capture = PendingCaptureEvent.objects.get(batch_id=preview["batch_id"])
                open_review(user=self.staff, capture=capture, mode="deferred")
                resolve_capture(user=self.staff, capture=capture, student=self.student,
                                reason="Reviewed identity only; recovery remains incomplete", timing_confirmed=True)
            close_session(user=self.staff, session=session)
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["rate_percent"], rate["eligible_recorded_meetings"], rate["pending_meetings"]), (None, 0, 2))

    def finalise(self, session, **changes):
        from .finalisation import inspect_finalisation, finalise_meeting
        snapshot = inspect_finalisation(user=self.staff, session=session)
        return finalise_meeting(**{**dict(user=self.staff, session=session,
            expected_digest=snapshot["review_sha256"], reviewed=True, reason="Reviewed confirmed attendance; unknown captures stay archived"), **changes})

    def test_explicit_finalisation_counts_confirmed_records_keeps_archives(self):
        from .services import close_session
        from .models import MeetingFinalisation
        session = self.session()
        capture = self.capture(session)
        close_session(user=self.staff, session=session)
        self.assertEqual(course_rates(user=self.staff, offering=self.offering)[0]["pending_meetings"], 1)
        first = self.finalise(session)
        self.assertTrue(first["finalised"])
        self.assertFalse(first["replayed"])
        self.assertTrue(self.finalise(session)["replayed"])
        self.assertEqual(MeetingFinalisation.objects.filter(session=session).count(), 1)
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["rate_percent"], rate["eligible_recorded_meetings"], rate["finalised_meetings"]), ("0.00", 1, 1))
        self.assertTrue(PendingCaptureEvent.objects.filter(pk=capture.pk).exists())
        self.assertFalse(hasattr(PendingCaptureEvent.objects.get(pk=capture.pk), "review"))
        open_review(user=self.staff, capture=capture, mode="deferred")
        resolve_capture(user=self.staff, capture=capture, student=self.student,
                        reason="Later staff identity and timing confirmation", timing_confirmed=True)
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["rate_percent"], rate["finalised_meetings"]), ("100.00", 1))
        first_record = MeetingFinalisation.objects.get(session=session)
        self.assertEqual(first_record.records_snapshot, [])
        self.assertEqual(first_record.student_ids, [str(self.student.pk)])

    def test_finalisation_requires_closed_reviewed_reason_and_authorised_staff(self):
        from .services import close_session
        from .models import MeetingFinalisation
        session = self.session()
        with self.assertRaises(ValidationError):
            self.finalise(session)
        close_session(user=self.staff, session=session)
        for changes in ({"reviewed": False}, {"reason": " "}, {"expected_digest": "0" * 64}):
            with self.assertRaises(ValidationError):
                self.finalise(session, **changes)
        with self.assertRaises(PermissionDenied):
            self.finalise(session, user=self.other)
        self.assertFalse(MeetingFinalisation.objects.exists())

    def test_new_import_stales_finalisation_and_old_digest_cannot_reapprove(self):
        from .services import close_session
        from .finalisation import inspect_finalisation
        session = self.session()
        self.capture(session)
        close_session(user=self.staff, session=session)
        original = self.finalise(session)
        self.capture(session)
        current = inspect_finalisation(user=self.staff, session=session)
        self.assertTrue(current["review_stale"])
        self.assertFalse(current["finalised"])
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["pending_meetings"], rate["stale_finalisation_meetings"], rate["rate_percent"]), (1, 1, None))
        with self.assertRaises(ValidationError):
            self.finalise(session, expected_digest=original["review_sha256"])
        renewed = self.finalise(session)
        self.assertEqual(renewed["revision"], 2)
        self.assertTrue(renewed["finalised"])

    def test_finalisation_exact_import_replay_keeps_review_valid(self):
        from .services import close_session
        from .finalisation import inspect_finalisation
        session = self.session()
        metadata = header(session.pk)
        data = pack(metadata, [event()])
        preview = preview_pending_batch(user=self.staff, session=session, data=data)
        kwargs = dict(user=self.staff, session=session, data=data, expected_sha256=preview["file_sha256"])
        import_pending_batch(**kwargs)
        close_session(user=self.staff, session=session)
        self.finalise(session)
        self.assertTrue(import_pending_batch(**kwargs)["replayed"])
        self.assertTrue(inspect_finalisation(user=self.staff, session=session)["finalised"])

    def test_finalisation_api_no_store_scope_and_stale_confirmed_records(self):
        from .services import close_session, correct_record
        session = self.session()
        fixtures.AttendanceTests.mark(self, session)
        close_session(user=self.staff, session=session)
        self.client.force_authenticate(self.staff)
        url = f"/api/attendance/sessions/{session.pk}/finalisation/"
        preview = self.client.get(url)
        self.assertEqual(preview.status_code, 200)
        self.assertIn("no-store", preview["Cache-Control"])
        payload = {"expected_digest": preview.data["review_sha256"], "reviewed": True, "reason": "Reviewed meeting"}
        record = AttendanceRecord.objects.get(session=session)
        correct_record(user=self.staff, record=record, status="absent", reason="Staff corrected record")
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        payload["expected_digest"] = self.client.get(url).data["review_sha256"]
        final = self.client.post(url, payload, format="json")
        self.assertEqual(final.status_code, 200)
        self.assertTrue(final.data["finalised"])
        self.assertIn("no-store", final["Cache-Control"])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 404)

    def test_empty_recovery_batches_can_be_reviewed_without_resolving_captures(self):
        from .services import close_session
        session = self.session()
        metadata = header(session.pk)
        metadata["interrupted_write_pending"] = True
        data = pack(metadata, [])
        preview = preview_pending_batch(user=self.staff, session=session, data=data)
        import_pending_batch(user=self.staff, session=session, data=data, expected_sha256=preview["file_sha256"])
        close_session(user=self.staff, session=session)
        self.finalise(session)
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["rate_percent"], rate["pending_meetings"]), ("0.00", 0))

    def excuse(self, session, **changes):
        from .excusals import decide_excusal
        return decide_excusal(**{**dict(user=self.staff, session=session, student=self.student,
            event_id=uuid.uuid4(), is_excused=True, reason="Formal excuse reviewed by assigned staff"), **changes})

    def test_formal_excuse_removes_both_numerator_and_denominator(self):
        from .services import close_session
        sessions = [self.session() for _ in range(3)]
        fixtures.AttendanceTests.mark(self, sessions[0])
        fixtures.AttendanceTests.mark(self, sessions[2])
        for session in sessions:
            close_session(user=self.staff, session=session)
        self.excuse(sessions[0])
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["meetings_attended"], rate["eligible_recorded_meetings"], rate["excused_meetings"], rate["rate_percent"]), (1, 2, 1, "50.00"))
        self.assertEqual(AttendanceRecord.objects.filter(session=sessions[0], status="present").count(), 1)

    def test_excused_pending_and_finalised_meeting_has_null_zero_denominator(self):
        from .services import close_session
        session = self.session()
        capture = self.capture(session)
        self.excuse(session)
        close_session(user=self.staff, session=session)
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["excused_meetings"], rate["pending_meetings"], rate["rate_percent"]), (1, 1, None))
        self.finalise(session)
        rate = course_rates(user=self.staff, offering=self.offering)[0]
        self.assertEqual((rate["excused_meetings"], rate["finalised_meetings"], rate["eligible_recorded_meetings"], rate["rate_percent"]), (1, 1, 0, None))
        self.assertTrue(PendingCaptureEvent.objects.filter(pk=capture.pk).exists())

    def test_excusal_grant_revoke_regrant_audit_and_event_conflicts(self):
        from .models import AttendanceExcusalAction, AttendanceExcusal
        self.approved = self.roster(ids=[self.student.pk, self.retaker.pk])
        session = self.session()
        event_id = uuid.uuid4()
        first, replayed = self.excuse(session, event_id=event_id)
        self.assertFalse(replayed)
        self.assertTrue(self.excuse(session, event_id=event_id)[1])
        for changes in ({"reason": "Different claim"}, {"is_excused": False}, {"student": self.retaker}):
            with self.assertRaises(ValidationError):
                self.excuse(session, event_id=event_id, **changes)
        with self.assertRaises(ValidationError):
            self.excuse(self.session(), event_id=event_id)
        self.excuse(session, is_excused=False, reason="Formal excuse revoked after review")
        old, replayed = self.excuse(session, event_id=event_id)
        self.assertTrue(replayed)
        self.assertFalse(old.excusal.is_excused)
        self.excuse(session, reason="Excuse granted after further review")
        self.assertEqual(AttendanceExcusalAction.objects.filter(excusal=first.excusal).count(), 3)
        self.assertTrue(AttendanceExcusal.objects.get(session=session).is_excused)
        for changes in ({"student": self.outsider}, {"reason": " "}, {"reason": "x" * 1001}):
            with self.assertRaises(ValidationError):
                self.excuse(session, **changes)
        with self.assertRaises(PermissionDenied):
            self.excuse(session, user=self.other)

    def test_excusal_changes_stale_preview_but_later_audit_preserves_source_approval(self):
        from .services import close_session
        from .finalisation import inspect_finalisation
        from .models import MeetingFinalisation
        session = self.session()
        fixtures.AttendanceTests.mark(self, session)
        close_session(user=self.staff, session=session)
        preview = inspect_finalisation(user=self.staff, session=session)
        self.excuse(session)
        with self.assertRaises(ValidationError):
            self.finalise(session, expected_digest=preview["review_sha256"])
        self.finalise(session)
        audit = MeetingFinalisation.objects.get(session=session)
        self.assertTrue(audit.excusals_snapshot[0]["is_excused"])
        self.assertIsNone(course_rates(user=self.staff, offering=self.offering)[0]["rate_percent"])
        self.excuse(session, is_excused=False, reason="Excuse explicitly revoked")
        current = inspect_finalisation(user=self.staff, session=session)
        self.assertTrue(current["finalised"])
        self.assertFalse(current["confirmed_excusals"][0]["is_excused"])
        self.assertTrue(current["last_reviewed_excusals"][0]["is_excused"])
        self.assertEqual(course_rates(user=self.staff, offering=self.offering)[0]["rate_percent"], "100.00")

    def test_excusal_api_scope_idempotency_and_present_absent_only(self):
        session = self.session()
        fixtures.AttendanceTests.mark(self, session)
        self.client.force_authenticate(self.staff)
        url = f"/api/attendance/sessions/{session.pk}/excusals/"
        payload = {"event_id": str(uuid.uuid4()), "student": str(self.student.pk), "is_excused": True, "reason": "Formal excuse"}
        grant = self.client.post(url, payload, format="json")
        self.assertEqual(grant.status_code, 200)
        self.assertTrue(grant.data["current_is_excused"])
        self.assertIn("no-store", grant["Cache-Control"])
        self.assertTrue(self.client.post(url, payload, format="json").data["replayed"])
        queue = self.client.get(url)
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.data["excusals"][0]["student_id"], str(self.student.pk))
        self.assertIn("no-store", queue["Cache-Control"])
        record = AttendanceRecord.objects.get(session=session)
        response = self.client.post(f"/api/attendance/records/{record.pk}/correct/", {"status": "late", "reason": "Time alone"}, format="json")
        self.assertEqual(response.status_code, 400)
        record.refresh_from_db()
        self.assertEqual(record.status, "present")
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 404)

    def test_retrospective_excuse_preserves_history_and_future_roster_eligibility(self):
        from .services import close_session
        session = self.session()
        close_session(user=self.staff, session=session)
        original_ids = list(session.student_ids)
        self.roster(ids=[self.student.pk, self.retaker.pk], revision=1)
        with self.assertRaises(ValidationError):
            self.excuse(session, student=self.retaker)
        action, _ = self.excuse(session, student=self.retaker, retrospective=True,
            reason="Registered late; earlier meeting formally excused")
        self.assertTrue(action.excusal.retrospective)
        self.assertEqual(action.eligibility_roster_revision, 2)
        session.refresh_from_db()
        self.assertEqual(session.student_ids, original_ids)
        self.assertFalse(AttendanceRecord.objects.filter(session=session, student=self.retaker).exists())
        rates = {row["student_id"]: row for row in course_rates(user=self.staff, offering=self.offering)}
        late = rates[str(self.retaker.pk)]
        self.assertEqual((late["retrospective_excused_meetings"], late["excused_meetings"], late["eligible_recorded_meetings"], late["rate_percent"]), (1, 0, 0, None))
        future = self.session()
        self.assertIn(str(self.retaker.pk), future.student_ids)
        fixtures.AttendanceTests.mark(self, future, student=self.retaker)
        close_session(user=self.staff, session=future)
        late = {row["student_id"]: row for row in course_rates(user=self.staff, offering=self.offering)}[str(self.retaker.pk)]
        self.assertEqual((late["meetings_attended"], late["eligible_recorded_meetings"], late["retrospective_excused_meetings"], late["rate_percent"]), (1, 1, 1, "100.00"))

    def test_retrospective_scope_outsider_and_current_removal_audit(self):
        from .models import AttendanceExcusalAction
        session = self.session()
        with self.assertRaises(ValidationError):
            self.excuse(session, student=self.outsider, retrospective=True)
        with self.assertRaises(ValidationError):
            self.excuse(session, retrospective=True)
        self.roster(ids=[self.student.pk, self.retaker.pk], revision=1)
        event_id = uuid.uuid4()
        kwargs = dict(student=self.retaker, retrospective=True, event_id=event_id)
        grant, _ = self.excuse(session, **kwargs)
        with self.assertRaises(PermissionDenied):
            self.excuse(session, student=self.retaker, retrospective=True, user=self.other)
        with self.assertRaises(ValidationError):
            self.excuse(session, student=self.retaker, event_id=event_id, retrospective=False)
        self.roster(ids=[self.student.pk], revision=2)
        self.assertTrue(self.excuse(session, **kwargs)[1])
        revoked, _ = self.excuse(session, student=self.retaker, retrospective=True,
            is_excused=False, reason="Explicit withdrawal after roster removal")
        self.assertEqual(revoked.eligibility_roster_revision, 2)
        self.assertFalse(self.excuse(session, **kwargs)[0].excusal.is_excused)
        with self.assertRaises(ValidationError):
            self.excuse(session, student=self.retaker, retrospective=True, reason="Cannot grant while removed")
        self.assertEqual(AttendanceExcusalAction.objects.filter(excusal=grant.excusal).count(), 2)

    def test_retrospective_excuse_finalisation_preview_audit_binding(self):
        from .services import close_session
        from .finalisation import inspect_finalisation
        session = self.session()
        close_session(user=self.staff, session=session)
        self.roster(ids=[self.student.pk, self.retaker.pk], revision=1)
        preview = inspect_finalisation(user=self.staff, session=session)
        self.excuse(session, student=self.retaker, retrospective=True, reason="Written late-registration excuse")
        with self.assertRaises(ValidationError):
            self.finalise(session, expected_digest=preview["review_sha256"])
        state = self.finalise(session)
        saved = state["last_reviewed_excusals"][0]
        self.assertTrue(saved["retrospective"])
        self.assertFalse(saved["historical_roster_member"])
        self.assertEqual(saved["eligibility_roster_revision"], 2)
        self.assertTrue(state["finalised"])

    def test_retrospective_excuse_api_explicit_scope_and_metadata(self):
        session = self.session()
        self.roster(ids=[self.student.pk, self.retaker.pk], revision=1)
        self.client.force_authenticate(self.staff)
        url = f"/api/attendance/sessions/{session.pk}/excusals/"
        payload = {"student": str(self.retaker.pk), "event_id": str(uuid.uuid4()),
                   "is_excused": True, "reason": "Late registration"}
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        response = self.client.post(url, {**payload, "retrospective": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["retrospective"])
        self.assertFalse(response.data["historical_roster_member"])
        self.assertEqual(response.data["eligibility_roster_revision"], 2)
        self.assertIn("no-store", response["Cache-Control"])
        listed = self.client.get(url)
        self.assertTrue(listed.data["excusals"][0]["retrospective"])
        self.assertEqual(self.client.post(url, {**payload, "retrospective": True}, format="json").data["replayed"], True)
