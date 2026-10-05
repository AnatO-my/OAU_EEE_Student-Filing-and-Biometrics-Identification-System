from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the standard student-access groups."

    def handle(self, *args, **options):
        group_actions = {
            "Student Readers": ["view"],
            "Student Editors": ["view", "add", "change"],
        }

        for group_name, actions in group_actions.items():
            codenames = [
                f"{action}_{model}"
                for action in actions
                for model in ["student", "guardian"]
            ]

            permissions = list(
                Permission.objects.filter(
                    content_type__app_label="students",
                    codename__in=codenames,
                )
            )

            if len(permissions) != len(codenames):
                raise CommandError(
                    "Student permissions are missing. "
                    "Apply database migrations before running this command."
                )

            group, _ = Group.objects.get_or_create(name=group_name)
            group.permissions.set(permissions)

            self.stdout.write(self.style.SUCCESS(f"Configured {group_name}"))
