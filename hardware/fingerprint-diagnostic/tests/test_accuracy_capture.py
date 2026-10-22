"""Synthetic protocol records only; no serial connection or fingerprints."""
import csv
import io
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import accuracy_capture as capture


def trial(**changes):
    row = dict(zip(capture.TRIAL_FIELDS, [
        "12345678-1", "identify_1toN", "auto", "genuine", "1", "scan", "1", "accepted", "TP",
        "7", "7", "0x00", "search", "150", "40", "3", "9", "150", "2000",
    ]))
    row.update(changes)
    return row


def summary(**changes):
    row = {key: "0" for key in capture.SUMMARY_FIELDS}
    row.update(session="12345678-1", test="identify_1toN", source="auto", case="combined",
               attempts="6", tp="2", fp="1", fn="1", tn="1", acquisition_errors="1", completed="5",
               accuracy_pct="60.0000", precision_pct="66.6667", recall_pct="66.6667",
               specificity_pct="50.0000", fpr_pct="50.0000", fnr_pct="33.3333", coverage_pct="83.3333")
    row.update(changes)
    return row


def line(tag, names, row):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow([tag] + [row[key] for key in names])
    return out.getvalue().encode("ascii")


def summary_group(session="12345678-1", poll_errors="0"):
    genuine = summary(session=session, case="genuine", attempts="4", tp="2", fp="0", fn="1", tn="0",
                      completed="3", accuracy_pct="66.6667", precision_pct="100.0000", recall_pct="66.6667",
                      specificity_pct="NA", fpr_pct="NA", fnr_pct="33.3333", coverage_pct="75.0000", poll_errors=poll_errors)
    impostor = summary(session=session, case="impostor", attempts="2", tp="0", fp="1", fn="0", tn="1",
                       acquisition_errors="0", completed="2", accuracy_pct="50.0000", precision_pct="0.0000",
                       recall_pct="NA", specificity_pct="50.0000", fpr_pct="50.0000", fnr_pct="NA", coverage_pct="100.0000")
    rows = [genuine, impostor, summary(session=session, poll_errors=poll_errors)]
    for case in ("genuine", "impostor", "combined"):
        row = {field: "0" for field in capture.SUMMARY_FIELDS}
        row.update(session=session, test="identify_1toN", source="manual", case=case)
        for field in capture.SUMMARY_FIELDS[16:]:
            row[field] = "NA"
        rows.append(row)
    return rows


def feed_group(store, rows):
    for row in rows:
        store.feed(line("ACCSUMMARY", capture.SUMMARY_FIELDS, row))


class CaptureTests(unittest.TestCase):
    def test_rtc_sync_waits_for_report_then_checks_actual_offset(self):
        with tempfile.TemporaryDirectory() as tmp, capture.Capture(Path(tmp) / "run") as store:
            store.feed(("ACCTIMEHEADER," + ",".join(capture.TIME_FIELDS) + "\n").encode())
            # Reopening a running board gets headers via h, not its startup time row.
            self.assertIsNone(capture.rtc_sync_command(store, 60))
            row = dict(zip(capture.TIME_FIELDS, ["12345678-1", "verify_1to1", "NA", "check", "NA", "io_error", "60", "2000"]))
            record = line("ACCTIME", capture.TIME_FIELDS, row)
            store.feed(record[:20])
            self.assertIsNone(capture.rtc_sync_command(store, 60))
            store.feed(record[20:])
            command = capture.rtc_sync_command(store, 60)
            self.assertRegex(command.decode(), r"^k20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\nz\n$")
            with self.assertRaisesRegex(ValueError, "firmware=60, requested=0"):
                capture.rtc_sync_command(store, 0)

    def test_rtc_sync_refuses_legacy_firmware(self):
        with self.assertRaisesRegex(ValueError, "RTC commands unavailable"):
            capture.rtc_sync_command(SimpleNamespace(clock_header_seen=False), 60)

    def test_rtc_rows_keep_missing_time_explicit_and_compare_to_host_utc(self):
        row = dict(zip(capture.TIME_FIELDS, ["12345678-1", "identify_1toN", "1", "trial",
                       "2026-10-15T15:00:00", "ok", "60", "2000"]))
        result = capture.timestamp_row(row)
        self.assertNotEqual(result["rtc_minus_host_seconds"], "NA")
        self.assertIn("+00:00", result["host_received_at_utc"])
        missing = capture.timestamp_row(dict(row, rtc_status="io_error", rtc_local_datetime="NA"))
        self.assertEqual(missing["rtc_minus_host_seconds"], "NA")
        for changes in ({"rtc_status": "io_error"}, {"rtc_local_datetime": "2026-02-30T15:00:00"},
                        {"rtc_utc_offset_minutes": "9999"}, {"scope": "check"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                capture.timestamp_row(dict(row, **changes))

    def test_timestamp_sidecar_joins_trials_and_flags_missing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            with capture.Capture(path) as store:
                store.feed(("ACCTIMEHEADER," + ",".join(capture.TIME_FIELDS) + "\n").encode())
                store.feed(line("ACCTRIAL", capture.TRIAL_FIELDS, trial()))
                rtc = dict(zip(capture.TIME_FIELDS, ["12345678-1", "identify_1toN", "1", "trial", "NA", "stopped", "60", "2000"]))
                store.feed(line("ACCTIME", capture.TIME_FIELDS, rtc))
                self.assertFalse(store.pending_trial_times)
                store.feed(line("ACCTRIAL", capture.TRIAL_FIELDS, trial(event_id="2")))
            self.assertIn("Missing RTC timestamp rows for 1", (path / "recording-issues.log").read_text())
            with (path / "timestamps.csv").open(newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["event_id"], rows[0]["rtc_status"]), ("1", "stopped"))

    def setUp(self):
        redirect = patch("sys.stderr", new_callable=io.StringIO)
        self.messages = redirect.start()
        self.addCleanup(redirect.stop)

    def test_shutdown_ignores_repeated_ctrl_c_and_finishes_after_six_rows(self):
        class Port:
            def __init__(self):
                self.writes = []

            def write(self, data):
                self.writes.append(data)

        port = Port()
        store = SimpleNamespace(summaries=12, complete_groups=2)
        handler = object()

        def receive():
            self.assertEqual(signals.call_args_list[0].args, (capture.signal.SIGINT, capture.signal.SIG_IGN))
            store.summaries += 1
            if store.summaries == 18:
                store.complete_groups += 1
            self.assertLessEqual(store.summaries, 18)  # No extra three-second read after complete replies.

        with patch.object(capture.signal, "signal", return_value=handler) as signals:
            capture.stop_and_collect(port, store, receive, True)
            self.assertEqual(signals.call_args_list[-1].args, (capture.signal.SIGINT, handler))
        self.assertEqual(port.writes, [b"p\ns\n"])
        self.assertEqual(store.summaries, 18)

    def test_shutdown_timeout_keeps_saved_rows_and_restores_handler_on_error(self):
        port = SimpleNamespace(write=lambda _: None)
        store = SimpleNamespace(summaries=4, complete_groups=0)
        with patch.object(capture.signal, "signal", return_value="previous") as signals:
            with patch.object(capture.time, "monotonic", side_effect=[0, 4]), patch("sys.stdout", new_callable=io.StringIO) as output:
                capture.stop_and_collect(port, store, lambda: self.fail("deadline expired"), True)
            self.assertIn("incomplete", output.getvalue())
            self.assertEqual(store.summaries, 4)
            self.assertEqual(signals.call_args_list[-1].args, (capture.signal.SIGINT, "previous"))

        def failure():
            raise OSError("synthetic serial error")

        with patch.object(capture.signal, "signal", return_value="previous") as signals:
            with self.assertRaises(OSError):
                capture.stop_and_collect(port, store, failure, True)
            self.assertEqual(signals.call_args_list[-1].args, (capture.signal.SIGINT, "previous"))

    def test_shutdown_before_handshake_only_pauses(self):
        writes = []
        port = SimpleNamespace(write=writes.append)
        with patch.object(capture.signal, "signal"):
            capture.stop_and_collect(port, SimpleNamespace(summaries=0), lambda: self.fail("no summary expected"), False)
        self.assertEqual(writes, [b"p\n"])

    def test_fragmented_records_headers_and_latest_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            with capture.Capture(path) as store:
                store.feed(b'boot noise "unclosed quote\n\xff\x01\n')
                store.feed(("ACCHEADER," + ",".join(capture.TRIAL_FIELDS) + "\n").encode())
                record = line("ACCTRIAL", capture.TRIAL_FIELDS, trial())
                for byte in record:
                    store.feed(bytes([byte]))
                feed_group(store, summary_group())
                feed_group(store, summary_group(poll_errors="3"))
                self.assertEqual((store.trials, store.summaries, store.complete_groups), (1, 12, 2))
            with (path / "trials.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows, [trial()])
            with (path / "latest-summary.csv").open(newline="") as f:
                self.assertEqual(list(csv.DictReader(f)), summary_group(poll_errors="3"))
            self.assertIn("boot noise", (path / "console.log").read_text())

    def test_invalid_summary_counts_and_rates(self):
        for changes in ({"attempts": "7"}, {"completed": "6"}, {"accuracy_pct": "99"},
                        {"coverage_pct": "nan"}, {"tp": "-1"}, {"wrong_id": "2"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                capture.validate_summary(summary(**changes))

    def test_zero_denominators_are_na(self):
        row = {key: "0" for key in capture.SUMMARY_FIELDS}
        row.update(session="12345678-1", test="verify_1to1", source="manual", case="combined")
        for key in capture.SUMMARY_FIELDS[16:]:
            row[key] = "NA"
        capture.validate_summary(row)
        with self.assertRaises(ValueError):
            capture.validate_summary(dict(row, accuracy_pct="0"))

    def test_manual_observations_cannot_be_double_counted(self):
        capture.validate_trial(trial(source="manual", counted="0"))
        capture.validate_trial(trial(source="manual", event_type="manual_key", returned_slot="NA"))
        for changes in ({"source": "manual", "counted": "1"}, {"counted": "0"},
                        {"event_type": "manual_key"}, {"outcome": "rejected", "class": "TP"},
                        {"returned_slot": "65536"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                capture.validate_trial(trial(**changes))

    def test_cases_and_sources_stay_separate(self):
        with tempfile.TemporaryDirectory() as tmp, capture.Capture(Path(tmp) / "run") as store:
            for session in ("12345678-1", "12345678-2"):
                feed_group(store, summary_group(session=session))
            self.assertEqual(len(store.latest), 12)
        with self.assertRaises(ValueError):
            capture.validate_summary(summary(case="genuine"))

    def test_bad_width_schema_and_oversized_lines_preserve_raw_log(self):
        for data in (b"ACCTRIAL,too,few,fields\n", b"ACCHEADER,wrong,schema\n", b"x" * 8193):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "run"
                with capture.Capture(path) as store, self.assertRaises(ValueError):
                    store.feed(data)
                self.assertEqual((path / "console.log").read_bytes(), data)

    def test_existing_capture_folder_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                capture.Capture(Path(tmp))

    def test_partial_summary_never_replaces_a_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            with capture.Capture(path) as store:
                feed_group(store, summary_group())
                previous = (path / "latest-summary.csv").read_bytes()
                for row in summary_group(poll_errors="9")[:2]:
                    store.feed(line("ACCSUMMARY", capture.SUMMARY_FIELDS, row))
                self.assertEqual((path / "latest-summary.csv").read_bytes(), previous)
                self.assertEqual(store.complete_groups, 1)
            self.assertIn("incomplete summary group", (path / "recording-issues.log").read_text())

    def test_combined_summary_must_equal_its_cases(self):
        with tempfile.TemporaryDirectory() as tmp, capture.Capture(Path(tmp) / "run") as store:
            rows = summary_group()
            # The row is individually valid, but its cases are nonzero.
            rows[2] = dict(rows[-1], source="auto")
            with self.assertRaisesRegex(ValueError, "Combined summary"):
                feed_group(store, rows)
            self.assertEqual(store.complete_groups, 0)
            self.assertFalse((store.directory / "latest-summary.csv").exists())

    def test_access_denied_snapshot_does_not_stop_trial_or_history_recording(self):
        with tempfile.TemporaryDirectory() as tmp, capture.Capture(Path(tmp) / "run") as store:
            with patch.object(Path, "replace", side_effect=PermissionError("synthetic access denied")):
                feed_group(store, summary_group())
                store.feed(line("ACCTRIAL", capture.TRIAL_FIELDS, trial()))
                self.assertTrue(store.snapshot_pending)
                self.assertEqual((store.trials, store.summaries, store.complete_groups), (1, 6, 1))
            store.retry_snapshot()
            self.assertFalse(store.snapshot_pending)
            with (store.directory / "latest-summary.csv").open(newline="") as f:
                self.assertEqual(list(csv.DictReader(f)), summary_group())

    def test_corrupt_prefix_and_missing_event_are_reported_without_inventing_a_row(self):
        with tempfile.TemporaryDirectory() as tmp, capture.Capture(Path(tmp) / "run") as store:
            store.feed(line("ACCTRIAL", capture.TRIAL_FIELDS, trial()))
            store.feed(b"\xff" * 64 + b",auto,genuine,2,scan,1,accepted,TP\n")
            store.feed(line("ACCTRIAL", capture.TRIAL_FIELDS, trial(event_id="3")))
            self.assertEqual(store.trials, 2)
            self.assertEqual(store.trial_gaps[0][1:], (2, 2))
            self.assertIn("Non-ASCII serial", self.messages.getvalue())
            self.assertIn("Missing trial events 2..2", self.messages.getvalue())

    def test_duplicate_event_is_not_counted_twice_and_summary_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp, capture.Capture(Path(tmp) / "run") as store:
            record = line("ACCTRIAL", capture.TRIAL_FIELDS, trial())
            store.feed(record)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                store.feed(record)
            self.assertEqual(store.trials, 1)
            feed_group(store, summary_group())
            self.assertIn("firmware reports 4 attempts but this trial CSV contains 1", self.messages.getvalue())

    def test_actual_cpp_firmware_csv_round_trip(self):
        executables = [Path(__file__).resolve().parents[1] / ".pio/host-tests" / f"accuracy_firmware_{v}_test.exe" for v in (0, 1)]
        if not all(p.exists() for p in executables):
            self.skipTest("Run tools/check_host.ps1 to compile both native firmware simulations first")
        for executable in executables:
            with self.subTest(variant=executable.name), tempfile.TemporaryDirectory() as tmp:
                transcript = subprocess.check_output([str(executable), "--transcript"])
                with capture.Capture(Path(tmp) / "run") as store:
                    store.feed(transcript)
                    self.assertEqual(store.trials, 5)  # Two scans plus three manual tallies.
                    self.assertEqual(store.summaries, 6)
                    self.assertEqual(len(store.headers), 2)
                    automatic = next(v for v in store.latest.values() if v["source"] == "auto" and v["case"] == "combined")
                    manual = next(v for v in store.latest.values() if v["source"] == "manual" and v["case"] == "combined")
                    self.assertEqual((automatic["tp"], automatic["tn"], automatic["attempts"]), ("1", "1", "2"))
                    self.assertEqual((manual["fp"], manual["tn"], manual["unclassified"], manual["attempts"]), ("1", "1", "1", "3"))
                    self.assertFalse(store.pending_trial_times)
                with (Path(tmp) / "run/timestamps.csv").open(newline="") as file:
                    times = [r for r in csv.DictReader(file) if r["scope"] == "trial"]
                self.assertEqual(len(times), 5)
                self.assertEqual([r["event_id"] for r in times], ["1", "2", "3", "4", "5"])


if __name__ == "__main__":
    unittest.main()
