"""Synthetic timer checks: no serial device, biometric files or network."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import timing_session


class TimingTests(unittest.TestCase):
    def test_success_duration_and_no_payload(self):
        records = []
        ticks = iter((1_000_000, 4_500_000))
        call = timing_session.measured(lambda value: value, "transfer", records, lambda: next(ticks))
        self.assertEqual(call(b"SYNTHETIC-SECRET"), b"SYNTHETIC-SECRET")
        self.assertEqual(records, [{"phase": "transfer", "elapsed_ms": 3.5, "completed": True}])
        self.assertNotIn("SECRET", json.dumps(records))

    def test_failed_duration_retained(self):
        records = []
        def fail():
            raise ValueError("SYNTHETIC-SECRET")
        with self.assertRaises(ValueError):
            timing_session.measured(fail, "transfer", records)()
        self.assertFalse(records[0]["completed"])
        self.assertNotIn("SECRET", json.dumps(records))

    def test_existing_tool_reused_console_private_and_restored(self):
        module = SimpleNamespace()
        def receive(*args):
            print("SYNTHETIC-SECRET")
            return b"synthetic"
        module.receive_batch = receive
        module.save_download = lambda *args: None
        def main():
            module.receive_batch()
            module.save_download()
        module.main = main
        argv = sys.argv
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "new"
            console = io.StringIO()
            with redirect_stdout(console):
                result = timing_session.run("deferred-download", ["download", "--port", "SYNTHETIC"],
                                            destination, loader=lambda name: module)
            metadata = json.loads((destination / "timing-metadata.json").read_text())
            self.assertEqual(result, 0)
            self.assertTrue(metadata["completed"])
            self.assertEqual(len(metadata["phases"]), 2)
            self.assertNotIn("SECRET", json.dumps(metadata))
            self.assertEqual(console.getvalue(), "")
            self.assertIn("SECRET", (destination / "console-private.log").read_text())
        self.assertIs(sys.argv, argv)
        self.assertIs(module.receive_batch, receive)

    def test_failure_not_reported_as_completed(self):
        module = SimpleNamespace(compare_probe=lambda: None, save_new=lambda: None)
        module.main = lambda: (_ for _ in ()).throw(SystemExit("SYNTHETIC-SECRET"))
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "new"
            result = timing_session.run("probe-compare", ["compare"], destination, loader=lambda name: module)
            self.assertEqual(result, 1)
            metadata = json.loads((destination / "timing-metadata.json").read_text())
            self.assertFalse(metadata["completed"])
            self.assertNotIn("SECRET", json.dumps(metadata))

    def test_destructive_and_wrong_subcommands_never_imported(self):
        def forbidden(name):
            self.fail("Invalid request imported a hardware tool")
        with tempfile.TemporaryDirectory() as folder:
            for arguments in (["initialize-empty"], ["export", "--all"], ["export", "--new-gallery"]):
                with self.assertRaises(ValueError):
                    timing_session.run("reference-export", arguments, Path(folder) / "new", loader=forbidden)


if __name__ == "__main__":
    unittest.main()
