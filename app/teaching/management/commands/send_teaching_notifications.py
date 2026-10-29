"""Explicit, bounded announcement delivery with graceful supervisor shutdown."""
import math
from pathlib import Path
import signal
import threading
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from teaching.models import Notification
from teaching.services import send_notification


class Command(BaseCommand):
    help = "Send pending link-only teaching notifications; never retry unknown outcomes."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=float, default=5)
        parser.add_argument("--stop-file", help="Finish the current email before stopping when this supervisor marker appears.")

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        if not math.isfinite(options["interval"]) or not 0 < options["interval"] <= 300:
            raise CommandError("--interval must be greater than 0 and at most 300 seconds.")
        if options["stop_file"] and not options["watch"]:
            raise CommandError("--stop-file requires --watch.")
        if settings.EMAIL_BACKEND in {"django.core.mail.backends.console.EmailBackend", "django.core.mail.backends.dummy.EmailBackend", "django.core.mail.backends.filebased.EmailBackend"}:
            raise CommandError("Configure a delivery email backend before processing announcement notifications.")
        stop_file = Path(options["stop_file"]) if options["stop_file"] else None
        stop_event = threading.Event()

        def stopping():
            return stop_event.is_set() or (stop_file is not None and stop_file.exists())

        def wait_for_next_pass():
            deadline = time.monotonic() + options["interval"]
            while not stopping():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                stop_event.wait(min(remaining, 0.25))
            return True

        previous = {}
        if options["watch"]:
            for name in (signal.SIGINT, signal.SIGTERM):
                previous[name] = signal.getsignal(name)
                signal.signal(name, lambda *_: stop_event.set())
            self.stdout.write("Announcement notification worker running; a stop request finishes the current email.")
            self.stdout.flush()
        try:
            while True:
                if stopping():
                    break
                if options["watch"]:
                    close_old_connections()
                ids = list(Notification.objects.filter(state="pending").order_by("pk").values_list("pk", flat=True)[:options["limit"]])
                for pk in ids:
                    if stopping():
                        break
                    self.stdout.write(f"{pk}: {send_notification(pk)}")
                    self.stdout.flush()
                if not options["watch"] or wait_for_next_pass():
                    break
        finally:
            for name, handler in previous.items():
                signal.signal(name, handler)
            if options["watch"]:
                close_old_connections()
