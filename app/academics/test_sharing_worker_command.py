import io
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase

from .management.commands.process_result_shares import Command


class ResultWorkerCommandTests(SimpleTestCase):
    def test_channel_and_limit_are_forwarded_without_starting_a_daemon(self):
        with patch("academics.management.commands.process_result_shares.process_next", side_effect=[True, None]) as process:
            call_command("process_result_shares", channel="email", limit=3, stdout=io.StringIO(), skip_checks=True)
        self.assertEqual(process.call_count, 2)
        process.assert_called_with(channel="email")

    def test_invalid_bounds_stop_before_queue_access(self):
        for values in ({"limit": 0}, {"limit": 1001}, {"interval": 0},
                       {"interval": float("nan")}, {"interval": 301}):
            with self.subTest(values=values), patch("academics.management.commands.process_result_shares.process_next") as process:
                with self.assertRaises(CommandError):
                    call_command("process_result_shares", **values, skip_checks=True)
                process.assert_not_called()

    def test_watch_stop_finishes_current_delivery_without_claiming_another(self):
        command = Command()
        def finish():
            command._stop_event.set()
            return True
        with patch("academics.management.commands.process_result_shares.process_next", side_effect=lambda **_: finish()) as process:
            call_command(command, watch=True, channel="email", stdout=io.StringIO(), skip_checks=True)
        process.assert_called_once_with(channel="email")

    def test_supervisor_marker_finishes_current_delivery_before_stopping(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "stop"
            def finish(**kwargs):
                marker.touch()
                return True
            with patch("academics.management.commands.process_result_shares.process_next", side_effect=finish) as process:
                call_command("process_result_shares", watch=True, stop_file=str(marker), channel="email", stdout=io.StringIO(), skip_checks=True)
            process.assert_called_once_with(channel="email")

    def test_existing_supervisor_marker_does_not_claim_a_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "stop"
            marker.touch()
            with patch("academics.management.commands.process_result_shares.process_next") as process:
                call_command("process_result_shares", watch=True, stop_file=str(marker), stdout=io.StringIO(), skip_checks=True)
            process.assert_not_called()

    def test_stop_marker_requires_watch_mode(self):
        with self.assertRaisesMessage(CommandError, "requires --watch"):
            call_command("process_result_shares", stop_file="synthetic-stop-marker", skip_checks=True)
