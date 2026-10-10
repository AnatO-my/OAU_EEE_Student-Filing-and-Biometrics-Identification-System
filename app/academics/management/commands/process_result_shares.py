from django.core.management.base import BaseCommand, CommandError

from academics.sharing_worker import process_next


class Command(BaseCommand):
    help = "Submit up to --limit queued guardian reports. Run under a supervised worker/scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        count = 0
        for _ in range(options["limit"]):
            outcome = process_next()
            if outcome is None:
                break
            count += bool(outcome)
        self.stdout.write(f"Processed {count} delivery submissions. Check batch statuses for outcomes.")
