import uuid
from django.test import TestCase, override_settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import Permission
from accounts.models import AdviserAssignment
from . import tests as fixtures
from .test_pending_batches import header, event, pack
from .pending_services import preview_pending_batch, import_pending_batch
from .services import close_session
from .finalisation import inspect_finalisation, finalise_meeting
from .policy import set_policy, eligibility, exam_exception, enrol_reference
from .models import ScannerReference

@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class PolicyTests(TestCase):
    setUp = fixtures.AttendanceTests.setUp
    make_student = fixtures.AttendanceTests.make_student
    roster = fixtures.AttendanceTests.roster
    session = fixtures.AttendanceTests.session
    def finalise(self, session):
        close_session(user=self.staff, session=session)
        state = inspect_finalisation(user=self.staff, session=session)
        return finalise_meeting(user=self.staff, session=session, expected_digest=state["review_sha256"], reviewed=True, reason="Reviewed for policy")
    def test_exam_uses_only_current_finalised_meetings_and_audited_exception(self):
        session = self.session()
        set_policy(user=self.staff, offering=self.offering, event_id=uuid.uuid4(), minimum_percentage=75, reason="Course policy")
        close_session(user=self.staff, session=session)
        self.assertEqual(eligibility(user=self.staff, offering=self.offering)[0]["exam_status"], "unknown")
        self.finalise(session)
        row = eligibility(user=self.staff, offering=self.offering)[0]
        self.assertEqual((row["exam_status"], row["exam_allowed"]), ("restricted", False))
        event_id = uuid.uuid4()
        kwargs = dict(user=self.staff, offering=self.offering, student=self.student, event_id=event_id, enabled=True, reason="Approved formal exam exception")
        first = exam_exception(**kwargs)
        self.assertEqual(exam_exception(**kwargs).pk, first.pk)
        self.assertEqual(eligibility(user=self.staff, offering=self.offering)[0]["exam_status"], "exception_approved")
        with self.assertRaises(PermissionDenied):
            exam_exception(**{**kwargs, "user": self.other})
        with self.assertRaises(ValidationError):
            exam_exception(**{**kwargs, "student": self.outsider})
        exam_exception(**{**kwargs, "event_id": uuid.uuid4(), "enabled": False, "reason": "Exception withdrawn"})
        data = pack(header(session.pk), [event()])
        preview = preview_pending_batch(user=self.staff, session=session, data=data)
        import_pending_batch(user=self.staff, session=session, data=data, expected_sha256=preview["file_sha256"])
        self.assertEqual(eligibility(user=self.staff, offering=self.offering)[0]["exam_status"], "unknown")
    def test_own_visibility_threshold_and_policy_boundary(self):
        session = self.session()
        fixtures.AttendanceTests.mark(self, session)
        self.finalise(session)
        set_policy(user=self.staff, offering=self.offering, event_id=uuid.uuid4(), minimum_percentage=100, reason="Discretionary threshold")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/me/attendance-eligibility/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["student_id"], str(self.student.pk))
        self.assertEqual(response.data[0]["exam_status"], "eligible")
        self.assertEqual(self.client.get(f"/api/attendance/offerings/{self.offering.pk}/eligibility/").status_code, 403)
        with self.assertRaises(PermissionDenied):
            set_policy(user=self.other, offering=self.offering, event_id=uuid.uuid4(), minimum_percentage=50, reason="Not assigned")
        with self.assertRaises(ValidationError):
            set_policy(user=self.staff, offering=self.offering, event_id=uuid.uuid4(), minimum_percentage=101, reason="Invalid")
    def test_reference_replacement_retains_disabled_history_and_mapping(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_student", content_type__app_label="students"))
        AdviserAssignment.objects.create(staff=self.staff, academic_session="2026/2027", level=200)
        scanner = uuid.uuid4()
        first = enrol_reference(user=self.staff, student=self.student, scanner_uuid=scanner, reference_id="12")
        replacement = enrol_reference(user=self.staff, student=self.student, scanner_uuid=scanner, reference_id="12", replaces=first)
        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertEqual(first.disabled_by_id, self.staff.pk)
        self.assertEqual(replacement.replaces_id, first.pk)
        self.assertEqual(replacement.student_id, self.student.pk)
        self.assertEqual(enrol_reference(user=self.staff, student=self.student, scanner_uuid=scanner, reference_id="12", replaces=first).pk, replacement.pk)
        self.assertEqual(ScannerReference.objects.count(), 2)
        with self.assertRaises(PermissionDenied):
            enrol_reference(user=self.other, student=self.student, scanner_uuid=scanner, reference_id="13")

    def test_course_enrolment_staff_does_not_need_broad_student_profile_access(self):
        self.roster()
        self.client.force_authenticate(self.staff)
        response = self.client.get("/api/attendance/biometric-students/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data], [self.student.pk])
        first = enrol_reference(user=self.staff, student=self.student, scanner_uuid=uuid.uuid4(), reference_id="5")
        self.assertEqual(first.student_id, self.student.pk)
        with self.assertRaises(PermissionDenied):
            enrol_reference(user=self.staff, student=self.outsider, scanner_uuid=uuid.uuid4(), reference_id="8")
