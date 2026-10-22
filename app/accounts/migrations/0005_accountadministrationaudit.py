import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_hodmessage")]

    operations = [
        migrations.CreateModel(
            name="AccountAdministrationAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=30)),
                ("before", models.JSONField(default=dict)),
                ("after", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="account_administration_actions", to=settings.AUTH_USER_MODEL)),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="account_administration_history", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"], "default_permissions": ()},
        ),
    ]
