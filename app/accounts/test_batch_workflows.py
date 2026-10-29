"""Synthetic policy batch tests: no live mail, records, or documents."""
import io
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from students.models import Student, Guardian
from documents.models import StudentDocument
from documents.services import process_upload
from documents.workflow import review_document
from documents.tests import make_pdf, clear_scan_ocr
from documents.test_storage import isolate_document_storage
from .models import User, AdviserAssignment, StudentChangeRequest
from .batch_services import temporary_account, offer_handover, accept_handover, request_change, review_change, archive_student

@override_settings(CURRENT_ACADEMIC_SESSION='2026/2027', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BatchWorkflowTests(TestCase):

    def setUp(self):
        isolate_document_storage(self)
        self.hod = User.objects.create_superuser('batch-hod', 'hod@example.test', 'Synthetic!Cedar7295')
        self.staff = User.objects.create_user('batch-adviser', is_staff=True, password='Synthetic!Cedar7295')
        self.other = User.objects.create_user('other-staff', is_staff=True, password='Synthetic!Cedar7295')
        self.account = User.objects.create_user('batch-student', email='student@example.test', password='Synthetic!Cedar7295')
        self.student = Student.objects.create(user=self.account, identifier_type='matriculation', identifier_value='EEE/TEST/001', full_name='Synthetic Student', admission_year=2026, mode_of_admission='utme', current_level=100)
        AdviserAssignment.objects.create(staff=self.staff, academic_session='2026/2027', level=100)
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='students', codename__in=['view_student', 'change_student']))
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='documents', codename='add_studentdocument'))
        self.client = APIClient()

    def upload(self, user=None):
        with patch('documents.services.run_ocr', side_effect=clear_scan_ocr):
            return process_upload(student=self.student, uploaded_file=make_pdf(), document_type='jamb', uploaded_by=user or self.account)[0]

    def test_student_initial_replacement_approval_history_and_download(self):
        first = self.upload()
        candidate = self.upload()
        self.assertEqual((first.approval_state, candidate.approval_state), ('active', 'pending'))
        first.refresh_from_db()
        self.assertIsNone(first.superseded_at)
        with self.assertRaises(PermissionDenied):
            review_document(user=self.other, document=candidate, approve=True, reason='Reviewed')
        review_document(user=self.staff, document=candidate, approve=True, reason='Clear replacement')
        first.refresh_from_db()
        self.assertEqual(first.approval_state, 'archived')
        self.client.force_authenticate(self.account)
        response = self.client.get(f'/api/documents/{first.pk}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        response.close()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/documents/{first.pk}/download/').status_code, 404)

    def test_rejected_resubmission_and_stale_replacement(self):
        first = self.upload()
        candidate = self.upload()
        review_document(user=self.staff, document=candidate, approve=False, reason='Wrong page')
        fresh = self.upload()
        staff_version = self.upload(self.staff)
        with self.assertRaises(ValidationError):
            review_document(user=self.staff, document=fresh, approve=True, reason='Reviewed')
        first.refresh_from_db()
        self.assertEqual(first.approval_state, 'archived')
        self.assertEqual(StudentDocument.objects.filter(approval_state='active').count(), 1)

    def test_contact_change_pending_approval_and_stale_proposal(self):
        row = request_change(user=self.account, student=self.student, kind='contact', values={'email': 'new@example.test'}, reason='New address')
        self.account.refresh_from_db()
        self.assertEqual(self.account.email, 'student@example.test')
        with self.assertRaises(PermissionDenied):
            review_change(user=self.other, row=row, approve=True, reason='Checked')
        review_change(user=self.staff, row=row, approve=True, reason='Confirmed')
        self.account.refresh_from_db()
        self.assertEqual(self.account.email, 'new@example.test')
        stale = request_change(user=self.account, student=self.student, kind='contact', values={'phone_number': '123'}, reason='New phone')
        self.student.phone_number = '456'
        self.student.save(update_fields=['phone_number'])
        with self.assertRaises(ValidationError):
            review_change(user=self.staff, row=stale, approve=True, reason='Checked')

    def test_guardian_and_identity_requests_retain_active_values_until_review(self):
        guardian = Guardian.objects.create(student=self.student, full_name='Synthetic Guardian', phone_number='123', relationship='parent')
        row = request_change(user=self.account, student=self.student, kind='guardian', values={'guardian_id': str(guardian.pk), 'phone_number': '456'}, reason='New phone')
        guardian.refresh_from_db()
        self.assertEqual(guardian.phone_number, '123')
        review_change(user=self.staff, row=row, approve=True, reason='Confirmed')
        guardian.refresh_from_db()
        self.assertEqual(guardian.phone_number, '456')
        row = request_change(user=self.account, student=self.student, kind='identity', values={'full_name': 'Correct Synthetic Name', 'programme': 'Electrical Engineering'}, reason='Correction')
        review_change(user=self.staff, row=row, approve=True, reason='Verified')
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, 'Correct Synthetic Name')
        self.assertEqual(self.student.programme, 'Electrical Engineering')

    def test_temporary_password_login_gate_change_and_csrf(self):
        self.student.user = None
        self.student.save(update_fields=['user'])
        result = temporary_account(actor=self.staff, student=self.student, email='newstudent@example.test')
        self.assertNotIn('password', result)
        password = mail.outbox[-1].body.split('Temporary password: ')[1].splitlines()[0]
        self.assertTrue(self.client.login(username=result['username'], password=password))
        self.assertEqual(self.client.get('/api/auth/csrf/').status_code, 200)
        self.assertTrue(self.client.get('/api/auth/me/').data['must_change_password'])
        self.assertEqual(self.client.get('/api/me/student/').status_code, 403)
        response = self.client.post('/api/auth/password/change/', {'current_password': password, 'new_password': 'Fresh!SyntheticCedar-7295'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get('/api/me/student/').status_code, 200)
        self.assertNotIn(password, str(list(User.objects.values('password'))))

    def test_temporary_email_failure_retains_recoverable_pending_account(self):
        self.student.user = None
        self.student.save(update_fields=['user'])
        with patch('accounts.batch_services.send_mail', side_effect=OSError('Synthetic transport uncertainty')):
            result = temporary_account(actor=self.staff, student=self.student, email='newstudent@example.test')
        self.assertEqual(result['delivery_status'], 'unknown')
        self.student.refresh_from_db()
        self.assertTrue(self.student.user.must_change_password)

    def test_handover_requires_incoming_acceptance_and_revokes_old_authority(self):
        row = offer_handover(actor=self.hod, target_id=self.staff.pk)
        self.hod.refresh_from_db()
        self.staff.refresh_from_db()
        self.assertTrue(self.hod.is_superuser)
        self.assertFalse(self.staff.is_superuser)
        with self.assertRaises(PermissionDenied):
            accept_handover(actor=self.other, handover_id=row.pk)
        accept_handover(actor=self.staff, handover_id=row.pk)
        self.hod.refresh_from_db()
        self.staff.refresh_from_db()
        self.assertFalse(self.hod.is_superuser)
        self.assertTrue(self.staff.is_superuser)
        self.assertEqual(accept_handover(actor=self.staff, handover_id=row.pk).pk, row.pk)

    def test_archive_preserves_records_and_disables_login(self):
        archive_student(actor=self.hod, student=self.student, reason='Student withdrew')
        self.student.refresh_from_db()
        self.account.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertFalse(self.account.is_active)
        self.assertTrue(Student.objects.filter(pk=self.student.pk).exists())

    def test_status_archive_also_disables_account(self):
        self.student.academic_status = 'withdrawn'
        self.student.save(update_fields=['academic_status'])
        self.account.refresh_from_db()
        self.student.refresh_from_db()
        self.assertFalse(self.account.is_active)
        self.assertFalse(self.student.is_active)

    def test_performance_review_retains_source_and_notifies_hod(self):
        import uuid
        from academics.models import AcademicSession
        from record_imports.models import ImportBatch,SourcePerformance
        from .batch_services import review_performance
        session=AcademicSession.objects.create(name="2026/2027")
        batch=ImportBatch.objects.create(owner=self.staff,request_id=uuid.uuid4(),kind="results",filename="synthetic.csv",file_sha256="a"*64,source_csv="",parsed_rows=[],preview={},preview_digest="b"*64)
        source=SourcePerformance.objects.create(batch=batch,student=self.student,academic_session=session,semester="harmattan",source={"gpa":"3.50"},comparison_at_import={"calculated":"3.75","status":"different"})
        with self.assertRaises(PermissionDenied):review_performance(actor=self.other,source=source,reason="Checked")
        row=review_performance(actor=self.staff,source=source,reason="Source retained; calculations checked")
        source.refresh_from_db()
        self.assertEqual(source.source,{"gpa":"3.50"})
        self.assertEqual(source.comparison_at_import,{"calculated":"3.75","status":"different"})
        self.assertEqual(source.review_status,"reviewed")
        self.assertTrue(row.notified_hod)
        self.assertEqual(mail.outbox[-1].to,[self.hod.email])

    def test_stale_hod_instance_cannot_approve_after_transfer(self):
        first=self.upload()
        pending=self.upload()
        offered=offer_handover(actor=self.hod,target_id=self.other.pk)
        accept_handover(actor=self.other,handover_id=offered.pk)
        self.assertTrue(self.hod.is_superuser)
        with self.assertRaises(PermissionDenied):
            review_document(user=self.hod,document=pending,approve=True,reason="Stale authority")

    def test_hod_can_correct_existing_matric_without_releasing_old_identity(self):
        from students.identity import identifier_is_unavailable
        original=self.student.identifier_value
        row=request_change(user=self.account,student=self.student,kind="identity",values={"identifier_value":"EEE/TEST/CORRECTED"},reason="Typographical error")
        with self.assertRaises(PermissionDenied):review_change(user=self.staff,row=row,approve=True,reason="Checked")
        review_change(user=self.hod,row=row,approve=True,reason="Document confirmed")
        self.student.refresh_from_db()
        self.assertEqual(self.student.identifier_value,"EEE/TEST/CORRECTED")
        self.assertTrue(identifier_is_unavailable(original))
        self.assertEqual(self.student.identity_changes.count(),1)
        self.assertEqual(self.student.identifier_aliases.count(),2)
        another=Student.objects.create(identifier_type="matriculation",identifier_value="EEE/OTHER",full_name="Other Student",admission_year=2026,mode_of_admission="utme",current_level=100)
        from students.services import correct_student_identifier
        from rest_framework.exceptions import ValidationError as APIValidationError
        with self.assertRaises(APIValidationError):correct_student_identifier(user=self.hod,student=another,identifier_value=original,expected_identifier_value=another.identifier_value)

    def test_review_reason_survives_hod_notification_failure(self):
        import uuid
        from academics.models import AcademicSession
        from record_imports.models import ImportBatch,SourcePerformance
        from .batch_services import review_performance
        session=AcademicSession.objects.create(name="2026/2027")
        batch=ImportBatch.objects.create(owner=self.staff,request_id=uuid.uuid4(),kind="results",filename="synthetic.csv",file_sha256="a"*64,source_csv="",parsed_rows=[],preview={},preview_digest="b"*64)
        source=SourcePerformance.objects.create(batch=batch,student=self.student,academic_session=session,semester="harmattan",source={"gpa":"3.50"},comparison_at_import={"calculated":"3.75"})
        with patch("accounts.batch_services.send_mail",side_effect=OSError("Synthetic SMTP uncertainty")):
            row=review_performance(actor=self.staff,source=source,reason="Retain this reason despite email failure")
        source.refresh_from_db();row.refresh_from_db()
        self.assertEqual(source.review_status,"reviewed")
        self.assertEqual(row.reason,"Retain this reason despite email failure")
        self.assertEqual(row.notification_state,"unknown")
        self.assertFalse(row.notified_hod)
