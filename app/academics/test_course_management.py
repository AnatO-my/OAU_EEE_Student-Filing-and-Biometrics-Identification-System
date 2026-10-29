from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from academics.models import AcademicSession, Course, CourseOffering, GradingScale
from attendance.models import CourseStaffAssignment


class CourseManagementAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.hod = User.objects.create_user(username='catalogue-hod', is_staff=True, is_superuser=True)
        self.staff = User.objects.create_user(username='catalogue-teacher', first_name='Course', last_name='Teacher', is_staff=True)
        self.student_user = User.objects.create_user(username='catalogue-student')
        self.year = AcademicSession.objects.create(name='2026/2027')
        self.course = Course.objects.create(code='EEE201', title='Circuit theory')
        self.offering = CourseOffering.objects.create(course=self.course, academic_session=self.year,
            semester='harmattan', level=200, credit_units=3)
        self.url = f'/api/attendance/offerings/{self.offering.pk}/staff/'

    def test_hod_can_create_catalogue_and_offering_with_published_scale(self):
        self.client.force_authenticate(self.hod)
        course = self.client.post('/api/courses/', {'code': 'EEE301', 'title': 'Electronics'}, format='json')
        self.assertEqual(course.status_code, 201)
        payload = {'course': course.data['id'], 'academic_session': self.year.pk,
            'semester': 'rain', 'level': 300, 'credit_units': 3, 'grading_scale': self.offering.grading_scale_id}
        response = self.client.post('/api/course-offerings/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['credit_units'], 3)
        self.assertEqual(self.client.post('/api/course-offerings/', payload, format='json').status_code, 400)
        draft = GradingScale.objects.create(name='Unpublished example', bands=self.offering.grading_scale.bands)
        payload.update(semester='harmattan', grading_scale=draft.pk)
        self.assertEqual(self.client.post('/api/course-offerings/', payload, format='json').status_code, 400)

    def test_listing_and_assignment_changes_use_existing_service(self):
        self.client.force_authenticate(self.hod)
        response = self.client.put(self.url, {'staff': self.staff.pk, 'is_active': True}, format='json')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['staff_name'], 'Course Teacher')
        self.assertTrue(response.data['results'][0]['staff_is_active'])
        self.assertNotIn('email', response.data['results'][0])
        self.assertEqual(self.client.put(self.url, {'staff': self.staff.pk, 'is_active': False}, format='json').status_code, 200)
        self.assertFalse(self.client.get(self.url).data['results'][0]['is_active'])
        self.assertEqual(CourseStaffAssignment.objects.filter(offering=self.offering, staff=self.staff).count(), 1)
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])
        self.assertFalse(self.client.get(self.url).data['results'][0]['staff_is_active'])
        self.assertEqual(self.client.put(self.url, {'staff': self.staff.pk, 'is_active': True}, format='json').status_code, 400)

    def test_catalogue_and_assignments_remain_hod_only(self):
        inactive = get_user_model().objects.create_user(username='inactive-hod', is_staff=True, is_superuser=True, is_active=False)
        for user in (None, self.staff, self.student_user, inactive):
            self.client.force_authenticate(user)
            with self.subTest(user=user):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.put(self.url, {'staff': self.staff.pk, 'is_active': True}, format='json').status_code, 403)
                self.assertEqual(self.client.post('/api/courses/', {'code': 'EEE999', 'title': 'Forbidden'}, format='json').status_code, 403)
                self.assertEqual(self.client.get('/api/course-offerings/').status_code, 403)
        self.assertFalse(Course.objects.filter(code='EEE999').exists())
        self.assertFalse(CourseStaffAssignment.objects.exists())

    def test_assignment_listing_is_scoped_to_offering_and_checks_missing_offering(self):
        self.client.force_authenticate(self.hod)
        CourseStaffAssignment.objects.create(offering=self.offering, staff=self.staff)
        another = CourseOffering.objects.create(course=self.course, academic_session=self.year,
            semester='rain', level=200, credit_units=3)
        self.assertEqual(self.client.get(f'/api/attendance/offerings/{another.pk}/staff/').data['results'], [])
        self.assertEqual(self.client.get('/api/attendance/offerings/999999/staff/').status_code, 404)

    @override_settings(CURRENT_ACADEMIC_SESSION='2026/2027')
    def test_assignment_makes_offering_available_to_teaching_selectors(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get('/api/teaching/courses/').data, [])
        self.client.force_authenticate(self.hod)
        self.assertEqual(self.client.put(self.url, {'staff': self.staff.pk, 'is_active': True}, format='json').status_code, 200)
        self.client.force_authenticate(self.staff)
        rows = self.client.get('/api/teaching/courses/').data
        self.assertEqual([row['id'] for row in rows], [self.offering.pk])
        self.assertEqual(rows[0]['course'], 'EEE201')
        self.client.force_authenticate(self.hod)
        self.client.put(self.url, {'staff': self.staff.pk, 'is_active': False}, format='json')
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get('/api/teaching/courses/').data, [])
