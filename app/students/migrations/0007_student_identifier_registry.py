from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def reserve_existing_identifiers(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    Registry = apps.get_model("students", "StudentIdentifier")
    alias = schema_editor.connection.alias
    reservations, seen = [], set()
    for student in Student.objects.using(alias).order_by("pk").iterator():
        value = student.identifier_value.strip()
        key = value.casefold()
        if not key or len(value) > 100 or not value.isprintable() or key in seen:
            raise RuntimeError("Student identity migration found blank, invalid or case/space-colliding identifiers. Resolve them explicitly before retrying; no students were merged or deleted.")
        seen.add(key)
        Student.objects.using(alias).filter(pk=student.pk).update(identifier_key=key)
        reservations.append(Registry(student_id=student.pk, identifier_type=student.identifier_type,
            identifier_value=student.identifier_value, identifier_key=key))
    Registry.objects.using(alias).bulk_create(reservations)


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0006_merge_academic_status_surname"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name="student", name="identifier_key",
            field=models.CharField(max_length=300, editable=False, null=True)),
        migrations.AlterField(model_name="student", name="phone_number",
            field=models.CharField(max_length=30, blank=True, default="")),
        migrations.CreateModel(name="StudentIdentifier", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("identifier_type", models.CharField(choices=[("matriculation", "Matriculation number"), ("utme", "UTME number")], max_length=20)),
            ("identifier_value", models.CharField(max_length=100)),
            ("identifier_key", models.CharField(max_length=300, unique=True, editable=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="identifier_aliases", to="students.student")),
        ]),
        migrations.CreateModel(name="StudentIdentityChange", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("previous_type", models.CharField(max_length=20)), ("previous_value", models.CharField(max_length=100)),
            ("identifier_type", models.CharField(max_length=20)), ("identifier_value", models.CharField(max_length=100)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="identity_changes", to="students.student")),
        ]),
        migrations.RunPython(reserve_existing_identifiers, migrations.RunPython.noop),
        migrations.AlterField(model_name="student", name="identifier_key",
            field=models.CharField(max_length=300, unique=True, editable=False)),
    ]
