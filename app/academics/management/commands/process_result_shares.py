from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
import math
from pathlib import Path
import signal
import threading
import time

from academics.sharing_worker import process_next


# Process a bounded number of queued guardian-report submissions for a supervised worker.
class Command(BaseCommand):
    help = "Submit up to --limit queued guardian reports. Run under a supervised worker/scheduler."

    # Configure the maximum number of delivery submissions handled in this invocation.
    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--channel", choices=("email", "whatsapp"),
                            help="Process only this channel; omit to process both.")
        parser.add_argument("--watch", action="store_true", help="Keep polling until stopped.")
        parser.add_argument("--interval", type=float, default=5,
                            help="Seconds between bounded processing passes in watch mode.")
        parser.add_argument("--stop-file", help="In watch mode, finish the current submission and stop when this supervisor marker exists.")

    # Validate the limit and process queued deliveries until the queue is empty or capped.
    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        if not math.isfinite(options["interval"]) or not 0 < options["interval"] <= 300:
            raise CommandError("--interval must be greater than 0 and at most 300 seconds.")
        if options["stop_file"] and not options["watch"]:
            raise CommandError("--stop-file requires --watch.")
        stop_file = Path(options["stop_file"]) if options["stop_file"] else None
        self._stop_event = threading.Event()
        def stopping():
            return self._stop_event.is_set() or (stop_file is not None and stop_file.exists())

        def wait_for_next_pass():
            # Poll a supervisor marker too: Windows processes without a console
            # cannot reliably receive Ctrl+C. Finish any in-flight delivery first.
            deadline = time.monotonic() + options["interval"]
            while not stopping():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._stop_event.wait(min(remaining, 0.25))
            return True
        previous = {}
        if options["watch"]:
            for name in (signal.SIGINT, signal.SIGTERM):
                previous[name] = signal.getsignal(name)
                signal.signal(name, lambda *_: self._stop_event.set())
            self.stdout.write("Result delivery worker running. Stop requests finish the current submission before exiting.")
            self.stdout.flush()
        try:
            while True:
                if options["watch"]:
                    close_old_connections()
                count = 0
                for _ in range(options["limit"]):
                    if stopping():
                        break
                    outcome = process_next(channel=options["channel"])
                    if outcome is None:
                        break
                    count += bool(outcome)
                if count or not options["watch"]:
                    self.stdout.write(f"Processed {count} delivery submissions. Check batch statuses for outcomes.")
                    self.stdout.flush()
                if not options["watch"] or wait_for_next_pass():
                    break
        finally:
            for name, handler in previous.items():
                signal.signal(name, handler)
            if options["watch"]:
                close_old_connections()
