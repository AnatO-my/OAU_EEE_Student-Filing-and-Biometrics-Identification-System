from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command

from rest_framework.test import APIClient
from accounts.models import AdviserAssignment
from .models import Guardian, Student


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class StudentAPItests(TestCase):

    # setUp method is used to create a test client, a staff user with the necessary permissions, and a sample student for testing.
    def setUp(self):
        self.client = APIClient()
        self.staff = get_user_model().objects.create_user(
            username="example-staff", password="synthetic-test-password", is_staff=True
        )
        AdviserAssignment.objects.create(
            staff=self.staff,
            academic_session="2026/2027",
            level=300,
        )
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="view_student",
        )
        self.staff.user_permissions.add(permission)
        self.student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="00123456",
            full_name="Example Student",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )

    # test_anonymous_and_nonstaff_are_denied method checks that anonymous users and non-staff users are denied access to the student API endpoints.
    def test_anonymous_and_nonstaff_are_denied(self):
        self.assertEqual(self.client.get("/api/students/").status_code, 403)
        user = get_user_model().objects.create_user(username="nonstaff")
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get("/api/students/").status_code, 403)

    # test_search_filters_and_detail method tests the search and filtering functionality of the student list API endpoint, as well as retrieving the details of a specific student.
    def test_search_filters_and_detail(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(
            "/api/students/",
            {"search": "Example", "current_level": 300, "is_active": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["identifier_value"], "00123456")
        self.assertEqual(
            self.client.get("/api/students/?current_level=200").data["count"], 0
        )
        detail = self.client.get(f"/api/students/{self.student.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(str(detail.data["student_id"]), str(self.student.pk))

    # test_invalid_filters_and_missing_student method checks that invalid filter values return a 400 status code and that requesting a non-existent student returns a 404 status code.
    def test_invalid_filters_and_missing_student(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.get("/api/students/?current_level=abc").status_code, 400
        )
        self.assertEqual(
            self.client.get("/api/students/?mode_of_admission=invalid").status_code, 400
        )
        self.assertEqual(
            self.client.get(
                "/api/students/00000000-0000-0000-0000-000000000000/"
            ).status_code,
            404,
        )

    # test_pagination method tests the pagination functionality of the student list API endpoint by creating multiple student records and verifying that the response contains the correct number of results per page and the presence of a next page link.
    def test_pagination(self):
        self.client.force_authenticate(self.staff)
        Student.objects.bulk_create(
            [
                Student(
                    identifier_type="matriculation",
                    identifier_value=f"TEST-{i}",
                    full_name=f"Student {i}",
                    phone_number="+2340000000000",
                    admission_year=2024,
                    mode_of_admission="utme",
                    current_level=300,
                )
                for i in range(20)
            ]
        )
        response = self.client.get("/api/students/")
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(
            len(self.client.get("/api/students/?page=2").data["results"]), 1
        )

    # test_staff_can_create_student_in_assigned_level method tests that a staff user with the appropriate permissions can successfully create a new student record in an assigned level, and verifies that the created student's details match the provided data.
    def test_staff_can_create_student_in_assigned_level(self):
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="add_student",
        )
        self.staff.user_permissions.add(permission)

        staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(staff)

        response = self.client.post(
            "/api/students/",
            {
                "identifier_type": "matriculation",
                "identifier_value": "CREATE-001",
                "full_name": "New Example Student",
                "phone_number": "+2340000000000",
                "admission_year": 2024,
                "mode_of_admission": "utme",
                "current_level": 300,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        student = Student.objects.get(identifier_value="CREATE-001")
        self.assertEqual(student.current_level, 300)
        self.assertEqual(student.full_name, "New Example Student")
        self.assertEqual(
            response.data["student_id"],
            str(student.pk),
        )
        self.assertIsNone(student.user)

    # test_multiple_guardians_protect_student method tests that a student with multiple associated guardians cannot be deleted due to the PROTECT constraint on the foreign key relationship.
    def test_multiple_guardians_protect_student(self):
        for name in ["Guardian A", "Guardian B"]:
            Guardian.objects.create(
                student=self.student,
                full_name=name,
                relationship="Guardian",
                phone_number="+2340000000000",
            )
        self.assertEqual(self.student.guardians.count(), 2)
        with self.assertRaises(ProtectedError):
            self.student.delete()

    # test_password_is_hashed method verifies that the password for the staff user is stored in a hashed format and can be correctly checked using the check_password method.
    def test_password_is_hashed(self):
        self.assertNotEqual(self.staff.password, "synthetic-test-password")
        self.assertTrue(self.staff.check_password("synthetic-test-password"))

    # test_reader_group_grants_student_access method tests that a user in the "Student Readers" group is granted access by the superuser to view student records after the group is set up and the user is added to it.
    def test_reader_group_grants_student_access(self):
        user = get_user_model().objects.create_user(
            username="restricted-staff",
            is_staff=True,
        )
        self.client.force_authenticate(user)

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 403)

        call_command("setup_staff_groups", verbosity=0)
        group = Group.objects.get(name="Student Readers")
        user.groups.add(group)

        # Reload to avoid Django's cached permission results.
        user = get_user_model().objects.get(pk=user.pk)
        self.client.force_authenticate(user)

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)

    # test_adviser_cannot_access_another_level method tests that an adviser assigned to a specific academic session and level cannot access student records outside of their assigned level, ensuring proper access control based on the adviser's assignment.
    def test_adviser_cannot_access_another_level(self):
        other = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="OUTSIDE-001",
            full_name="Outside Scope Student",
            phone_number="+2340000000000",
            admission_year=2023,
            mode_of_admission="utme",
            current_level=400,
        )
        self.client.force_authenticate(self.staff)

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)

        identifiers = [row["identifier_value"] for row in response.data["results"]]
        self.assertNotIn(other.identifier_value, identifiers)

        response = self.client.get(f"/api/students/{other.pk}/")
        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            "/api/students/",
            {"current_level": 400},
        )
        self.assertEqual(response.data["count"], 0)

    # test_revoked_assignment_removes_access method tests that when an adviser's assignment is revoked (set to inactive), they lose access to the student records they previously had access to, but not affecting other advisers or superusers who still have access. Their accounts still exist though.
    def test_revoked_assignment_removes_access(self):
        AdviserAssignment.objects.filter(
            staff=self.staff,
            academic_session="2026/2027",
            level=300,
        ).update(is_active=False)

        self.client.force_authenticate(self.staff)

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.client.get(f"/api/students/{self.student.pk}/")
        self.assertEqual(response.status_code, 404)

    # test_hod_can_access_students_without_assignment method tests that a superuser (Head of Department) can access all student records, including those without any adviser assignment, ensuring that superusers have unrestricted access to student data.
    def test_hod_can_access_students_without_assignment(self):
        hod = get_user_model().objects.create_superuser(
            username="example-hod",
            email="hod@example.com",
            password="synthetic-test-password",
        )
        other = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="HOD-TEST-001",
            full_name="Another Level Student",
            phone_number="+2340000000000",
            admission_year=2023,
            mode_of_admission="utme",
            current_level=400,
        )
        self.client.force_authenticate(hod)

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        response = self.client.get(f"/api/students/{other.pk}/")
        self.assertEqual(response.status_code, 200)

    # test_previous_session_assignment_does_not_grant_access method tests that an adviser assigned to a previous academic session does not have access to student records in the current session, ensuring that access is restricted based on the academic session of the adviser's assignment.
    def test_previous_session_assignment_does_not_grant_access(self):
        AdviserAssignment.objects.filter(
            staff=self.staff,
            academic_session="2026/2027",
            level=300,
        ).update(academic_session="2025/2026")

        self.client.force_authenticate(self.staff)

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.client.get(f"/api/students/{self.student.pk}/")
        self.assertEqual(response.status_code, 404)

    # test_student_can_read_own_profile_only method tests that a student user can only read their own profile and is denied access to the list of students or other students' profiles, ensuring that students cannot access data that does not belong to them.
    def test_student_can_read_own_profile_only(self):
        user = get_user_model().objects.create_user(
            username="example-student",
            password="synthetic-test-password",
            is_staff=False,
        )
        self.student.user = user
        self.student.save(update_fields=["user"])

        other = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="OTHER-001",
            full_name="Other Student",
            phone_number="+2340000000000",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )

        self.client.force_authenticate(user)

        response = self.client.get("/api/me/student/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["student_id"],
            str(self.student.pk),
        )

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/api/students/{other.pk}/")
        self.assertEqual(response.status_code, 403)

    # test_student_cannot_edit_own_profile method tests that a student user cannot edit their own profile, ensuring that students do not have permission to modify their own data through the API.
    def test_student_cannot_edit_own_profile(self):
        user = get_user_model().objects.create_user(
            username="readonly-student",
            is_staff=False,
        )
        self.student.user = user
        self.student.save(update_fields=["user"])

        self.client.force_authenticate(user)

        response = self.client.patch(
            "/api/me/student/",
            {"full_name": "Changed Name"},
            format="json",
        )
        self.assertEqual(response.status_code, 405)

        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Example Student")

    # test_staff_cannot_bypass_scope_through_django_admin method tests that staff users cannot access the Django admin interface for student-related models, ensuring that access control is enforced even in the admin interface.
    def test_staff_cannot_bypass_scope_through_django_admin(self):
        self.client.force_login(self.staff)
        for url in [
            "/admin/students/student/",
            "/admin/students/guardian/",
            "/admin/accounts/user/",
            "/admin/accounts/adviserassignment/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 403)

    # test_missing_session_does_not_grant_staff_access method tests that when the CURRENT_ACADEMIC_SESSION setting is missing or empty, staff users do not have access to student records, ensuring that access control is enforced based on the current academic session.
    @override_settings(CURRENT_ACADEMIC_SESSION="")
    def test_missing_session_does_not_grant_staff_access(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get("/api/students/").data["count"], 0)
        self.assertEqual(
            self.client.get(f"/api/students/{self.student.pk}/").status_code, 404
        )

    # test_staff_cannot_create_student_outside_assigned_level method tests that a staff user cannot create a new student record in a level they are not assigned to, ensuring that access control is enforced when creating new student records.
    def test_staff_cannot_create_student_outside_assigned_level(self):
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="add_student",
        )
        self.staff.user_permissions.add(permission)

        staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(staff)

        response = self.client.post(
            "/api/students/",
            {
                "identifier_type": "matriculation",
                "identifier_value": "DENIED-001",
                "full_name": "Outside Level Student",
                "phone_number": "+2340000000000",
                "admission_year": 2023,
                "mode_of_admission": "utme",
                "current_level": 400,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Student.objects.filter(
                identifier_value="DENIED-001"
            ).exists()
        )

    # test_staff_without_add_permission_cannot_create_student method tests that a staff user without the "add_student" permission cannot create a new student record, ensuring that access control is enforced based on user permissions.
    def test_staff_without_add_permission_cannot_create_student(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/students/",
            {
                "identifier_type": "matriculation",
                "identifier_value": "NO-PERMISSION-001",
                "full_name": "Example Student",
                "phone_number": "+2340000000000",
                "admission_year": 2024,
                "mode_of_admission": "utme",
                "current_level": 300,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Student.objects.filter(
                identifier_value="NO-PERMISSION-001"
            ).exists()
        )

    # test_hod_can_create_student_without_assignment method tests that a head of department can create a student record without being assigned as an adviser, ensuring that HODs have the appropriate permissions to manage student data.
    def test_hod_can_create_student_without_assignment(self):
        hod = get_user_model().objects.create_superuser(
            username="creating-hod",
            email="hod@example.com",
            password="synthetic-test-password",
        )
        self.client.force_authenticate(hod)

        response = self.client.post(
            "/api/students/",
            {
                "identifier_type": "matriculation",
                "identifier_value": "HOD-CREATE-001",
                "full_name": "HOD Created Student",
                "phone_number": "+2340000000000",
                "admission_year": 2023,
                "mode_of_admission": "transfer",
                "current_level": 400,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Student.objects.filter(
                identifier_value="HOD-CREATE-001",
                current_level=400,
            ).exists()
        )
        self.assertFalse(
            AdviserAssignment.objects.filter(staff=hod).exists()
        )

    # test_duplicate_identifier_is_rejected method tests that a student record with a duplicate identifier is rejected, ensuring data integrity.
    def test_duplicate_identifier_is_rejected(self):
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="add_student",
        )
        self.staff.user_permissions.add(permission)

        staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(staff)

        original_count = Student.objects.count()

        response = self.client.post(
            "/api/students/",
            {
                "identifier_type": "matriculation",
                "identifier_value": self.student.identifier_value,
                "full_name": "Duplicate Student",
                "phone_number": "+2340000000000",
                "admission_year": 2024,
                "mode_of_admission": "utme",
                "current_level": 300,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("identifier_value", response.data)
        self.assertEqual(Student.objects.count(), original_count)

        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Example Student")

    # test_session_creation_requires_csrf_token method tests that creating a student record requires a valid CSRF token, ensuring that CSRF protection is enforced for state-changing operations.
    def test_session_creation_requires_csrf_token(self):
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="add_student",
        )
        self.staff.user_permissions.add(permission)

        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)

        payload = {
            "identifier_type": "matriculation",
            "identifier_value": "CSRF-CREATE-001",
            "full_name": "Example Student",
            "phone_number": "+2340000000000",
            "admission_year": 2024,
            "mode_of_admission": "utme",
            "current_level": 300,
        }

        response = client.post(
            "/api/students/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Student.objects.filter(
                identifier_value="CSRF-CREATE-001"
            ).exists()
        )

        token = client.get("/api/auth/csrf/").data["csrfToken"]

        response = client.post(
            "/api/students/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)

    # test_staff_can_edit_student_in_assigned_level method tests that a staff user with the appropriate permissions can successfully edit an existing student record in an assigned level, and verifies that the updated student's details match the provided data.
    def test_staff_can_edit_student_in_assigned_level(self):
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="change_student",
        )
        self.staff.user_permissions.add(permission)

        staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(staff)

        response = self.client.patch(
            f"/api/students/{self.student.pk}/",
            {"phone_number": "+2348012345678"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.student.refresh_from_db()
        self.assertEqual(
            self.student.phone_number,
            "+2348012345678",
        )
        self.assertEqual(self.student.full_name, "Example Student")
        self.assertEqual(self.student.identifier_value, "00123456")
        self.assertEqual(self.student.current_level, 300)

   # test_staff_cannot_move_student_to_unassigned_level method tests that a staff user cannot change the current level of a student to a level they are not assigned to, ensuring that access control is enforced when updating student records.
    def test_staff_cannot_move_student_to_unassigned_level(self):
        permission = Permission.objects.get(
            content_type__app_label="students",
            codename="change_student",
        )
        self.staff.user_permissions.add(permission)

        staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_authenticate(staff)

        response = self.client.patch(
            f"/api/students/{self.student.pk}/",
            {
                "current_level": 400,
                "phone_number": "+2348012345678",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.student.refresh_from_db()
        self.assertEqual(self.student.current_level, 300)
        self.assertEqual(
            self.student.phone_number,
            "+2340000000000",
        )


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class StudentSurnameFieldTests(TestCase):
    #the surname is stored on its own because it doubles as the student's
    #first-login credential; these tests pin the field's behaviour before the
    #account creation and surname login flow is built on top of it

    def setUp(self):
        self.client = APIClient()
        self.staff = get_user_model().objects.create_user(
            username="example-staff-surname",
            is_staff=True,
        )
        self.student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="TEST-SURNAME-001",
            full_name="Example Ogunlade",
            surname="Ogunlade",
            phone_number="+2340000000001",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        AdviserAssignment.objects.create(
            staff=self.staff,
            academic_session="2026/2027",
            level=300,
        )
        permission = Permission.objects.get(codename="view_student")
        self.staff.user_permissions.add(permission)

    #the surname is kept exactly as typed, independent of the full name
    def test_surname_is_stored_separately_from_full_name(self):
        self.assertEqual(self.student.surname, "Ogunlade")
        self.assertEqual(self.student.full_name, "Example Ogunlade")

    #a student created without a surname keeps an empty value rather than a
    #token guessed from the full name, so surname login simply stays
    #unavailable until an administrator sets it
    def test_missing_surname_defaults_to_empty_and_is_not_guessed(self):
        student = Student.objects.create(
            identifier_type="matriculation",
            identifier_value="TEST-SURNAME-002",
            full_name="Adaeze Nwosu",
            phone_number="+2340000000002",
            admission_year=2024,
            mode_of_admission="utme",
            current_level=300,
        )
        self.assertEqual(student.surname, "")

    #while the surname doubles as the initial credential it must never appear
    #in staff api responses, otherwise any staff member who can read students
    #could impersonate a student before the forced password change
    def test_student_api_responses_do_not_expose_the_surname(self):
        self.client.force_authenticate(self.staff)
        list_response = self.client.get("/api/students/")
        detail_response = self.client.get(f"/api/students/{self.student.pk}/")
        self.assertNotIn("surname", list_response.data["results"][0])
        self.assertNotIn("surname", detail_response.data)
