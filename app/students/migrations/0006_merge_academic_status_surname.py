from django.db import migrations


class Migration(migrations.Migration):
    # Preserve both existing histories; neither branch changes the same field.
    dependencies = [
        ("students", "0004_student_surname"),
        ("students", "0005_alter_student_options"),
    ]

    operations = []
