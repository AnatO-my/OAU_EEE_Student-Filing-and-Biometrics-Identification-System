import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def create_mutex(apps, schema_editor):
    apps.get_model("record_imports", "ImportMutex").objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("students", "0007_student_identifier_registry"),
        ("academics", "0006_academicsessionselection_currentacademicsession"),
    ]
    operations = [
        migrations.CreateModel(name="ImportMutex", fields=[("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False))], options={"default_permissions": ()}),
        migrations.AddConstraint(model_name="importmutex", constraint=models.CheckConstraint(condition=models.Q(("id", 1)), name="single_record_import_mutex")),
        migrations.CreateModel(name="ImportBatch", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("request_id", models.UUIDField()),
            ("kind", models.CharField(choices=[("roster", "Roster"), ("results", "Results")], max_length=10)),
            ("filename", models.CharField(max_length=120)), ("file_sha256", models.CharField(max_length=64)),
            ("source_csv", models.TextField()), ("parsed_rows", models.JSONField()), ("preview", models.JSONField()),
            ("preview_digest", models.CharField(max_length=64)), ("revision", models.PositiveIntegerField(default=1)),
            ("status", models.CharField(default="preview", max_length=12)), ("receipt", models.JSONField(null=True)),
            ("commit_request", models.JSONField(null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)), ("committed_at", models.DateTimeField(null=True)),
            ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"default_permissions": (), "ordering": ["-created_at", "-id"]}),
        migrations.AddConstraint(model_name="importbatch", constraint=models.UniqueConstraint(fields=("owner", "request_id"), name="unique_record_import_request")),
        migrations.CreateModel(name="ImportChange", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("row_number", models.PositiveIntegerField()), ("action", models.CharField(max_length=20)),
            ("before", models.JSONField()), ("after", models.JSONField()), ("reason", models.CharField(blank=True, max_length=1000)),
            ("batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="changes", to="record_imports.importbatch")),
            ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="students.student")),
            ("result", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to="academics.result")),
        ], options={"default_permissions": ()}),
        migrations.AddConstraint(model_name="importchange", constraint=models.UniqueConstraint(fields=("batch", "row_number"), name="unique_record_import_change_row")),
        migrations.RunPython(create_mutex, migrations.RunPython.noop),
    ]
