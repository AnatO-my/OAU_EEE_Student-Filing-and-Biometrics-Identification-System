from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class GradingHistoryMigrationTests(TransactionTestCase):
    def test_existing_results_keep_initial_scale_and_values(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [("academics", "0001_initial"), ("students", "0004_student_surname")]
        try:
            executor.migrate(old_target)
            old_apps = executor.loader.project_state(old_target).apps
            Student = old_apps.get_model("students", "Student")
            Session = old_apps.get_model("academics", "AcademicSession")
            Course = old_apps.get_model("academics", "Course")
            Offering = old_apps.get_model("academics", "CourseOffering")
            Result = old_apps.get_model("academics", "Result")
            student = Student.objects.create(identifier_type="matriculation", identifier_value="000123",
                full_name="Migration example", phone_number="08000000000", admission_year=2024,
                mode_of_admission="utme", current_level=300)
            session = Session.objects.create(name="2026/2027")
            course = Course.objects.create(code="EEE301", title="Example")
            offering = Offering.objects.create(course=course, academic_session=session,
                semester="harmattan", level=300, credit_units=3)
            result = Result.objects.create(student=student, offering=offering,
                score=Decimal("68.00"), credit_units=3, is_verified=True)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            new_apps = executor.loader.project_state(latest).apps
            migrated = new_apps.get_model("academics", "Result").objects.get(pk=result.pk)
            scale = new_apps.get_model("academics", "GradingScale").objects.get(pk=migrated.grading_scale_id)
            new_offering = new_apps.get_model("academics", "CourseOffering").objects.get(pk=offering.pk)
            self.assertEqual(scale.name, "Initial five-point scale")
            self.assertTrue(scale.is_published)
            self.assertEqual(new_offering.grading_scale_id, scale.pk)
            self.assertEqual(migrated.score, Decimal("68.00"))
            self.assertEqual(migrated.credit_units, 3)
            self.assertTrue(migrated.is_verified)
            self.assertEqual(migrated.student_id, student.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
