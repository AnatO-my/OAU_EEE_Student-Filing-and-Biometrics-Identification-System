"""Capture the accuracy sketch's console and validated CSV records (no templates).

Windows: keyboard input is forwarded immediately; Enter terminates t <ID>.
The program is separate from Serial Monitor and needs exclusive port access.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone, timedelta
import math
import os
from pathlib import Path
import re
import signal
import sys
import time
import uuid

TRIAL_FIELDS = "session test source case event_id event_type counted outcome class expected_slot returned_slot scanner_code stage total_ms search_ms security gallery_count capacity uptime_ms".split()
SUMMARY_FIELDS = "session test source case attempts tp fp fn tn acquisition_errors communication_errors sensor_errors unclassified wrong_id poll_errors completed accuracy_pct precision_pct recall_pct specificity_pct fpr_pct fnr_pct coverage_pct".split()
SUMMARY_ORDER = [(s, c) for s in ("auto", "manual") for c in ("genuine", "impostor", "combined")]
TIME_FIELDS = "session test event_id scope rtc_local_datetime rtc_status rtc_utc_offset_minutes uptime_ms".split()
SAVED_TIME_FIELDS = TIME_FIELDS + ["host_received_at_utc", "rtc_minus_host_seconds"]


def timestamp_row(row):
    common(dict(row, source="auto"))
    if row["scope"] not in {"trial", "check"} or row["rtc_status"] not in {"ok", "io_error", "stopped", "invalid", "stalled", "backward"}:
        raise ValueError("Unknown RTC scope/status")
    number(row["uptime_ms"], maximum=(1 << 32) - 1)
    if row["scope"] == "trial":
        if not number(row["event_id"]):
            raise ValueError("RTC trial needs an event ID")
    elif row["event_id"] != "NA":
        raise ValueError("RTC check must not claim a trial ID")
    if not re.fullmatch(r"-?[0-9]+", row["rtc_utc_offset_minutes"]):
        raise ValueError("Invalid RTC UTC offset")
    offset = int(row["rtc_utc_offset_minutes"])
    if not -840 <= offset <= 840:
        raise ValueError("RTC UTC offset out of range")
    host = datetime.now(timezone.utc)
    delta = "NA"
    if row["rtc_status"] in {"ok", "stalled", "backward"}:
        stamp = row["rtc_local_datetime"]
        if not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", stamp):
            raise ValueError("Invalid RTC calendar timestamp")
        rtc = datetime.fromisoformat(stamp).replace(tzinfo=timezone(timedelta(minutes=offset)))
        delta = f"{(rtc - host).total_seconds():.3f}"
    elif row["rtc_local_datetime"] != "NA":
        raise ValueError("Unavailable RTC time must be NA")
    return dict(row, host_received_at_utc=host.isoformat(timespec="milliseconds"), rtc_minus_host_seconds=delta)


def rtc_sync_command(store, offset):
    """None means request a fresh z report; never guess an unreported offset."""
    if not store.clock_header_seen:
        raise ValueError("RTC commands unavailable; upload updated accuracy firmware")
    if store.clock_offset is None:
        return None
    if store.clock_offset != offset:
        raise ValueError(f"RTC offset differs: firmware={store.clock_offset}, requested={offset} minutes; refusing to set the wrong local time")
    local = datetime.now(timezone.utc) + timedelta(minutes=offset)
    return f"k{local:%Y-%m-%dT%H:%M:%S}\nz\n".encode("ascii")


def number(text, *, maximum=(1 << 64) - 1):
    if not re.fullmatch(r"[0-9]+", text) or int(text) > maximum:
        raise ValueError(f"Invalid unsigned field: {text!r}")
    return int(text)


def common(row):
    if (not re.fullmatch(r"[0-9A-Fa-f]{8}-[0-9]+", row["session"])
            or row["test"] not in {"identify_1toN", "verify_1to1"}
            or row["source"] not in {"auto", "manual"}):
        raise ValueError("Unknown accuracy session/test/source")


def validate_trial(row):
    common(row)
    if row["case"] not in {"genuine", "impostor"}:
        raise ValueError("Unknown ground-truth case")
    truth = row["case"] == "genuine"
    expected = {
        "accepted": "TP" if truth else "FP", "rejected": "FN" if truth else "TN",
        "wrong_identity": "FN", "acquisition_error": "NA", "communication_error": "NA",
        "sensor_error": "NA", "unclassified": "NA",
    }
    if row["outcome"] not in expected or row["class"] != expected[row["outcome"]]:
        raise ValueError("Outcome/classification disagreement")
    if row["outcome"] == "wrong_identity" and not truth:
        raise ValueError("wrong_identity belongs to genuine identification trials")
    if row["event_type"] not in {"scan", "manual_key"} or row["counted"] not in {"0", "1"}:
        raise ValueError("Unknown event/count flag")
    counted = row["source"] == "auto" or row["event_type"] == "manual_key"
    if row["counted"] != str(int(counted)) or (row["event_type"] == "manual_key" and row["source"] != "manual"):
        raise ValueError("Automatic/manual double-count guard failed")
    for field in ("event_id", "total_ms", "security", "gallery_count", "capacity", "uptime_ms"):
        number(row[field])
    for field in ("expected_slot", "returned_slot"):
        if row[field] != "NA":
            number(row[field], maximum=65535)
    if row["search_ms"] != "NA":
        number(row["search_ms"], maximum=(1 << 32) - 1)
    if row["scanner_code"] != "NA" and not re.fullmatch(r"0x[0-9A-F]{2}", row["scanner_code"]):
        raise ValueError("Invalid scanner confirmation code")
    if number(row["gallery_count"]) > number(row["capacity"]):
        raise ValueError("Gallery exceeds capacity")


def validate_summary(row):
    common(row)
    if row["case"] not in {"genuine", "impostor", "combined"}:
        raise ValueError("Unknown summary case")
    n = {key: number(row[key]) for key in SUMMARY_FIELDS[4:16]}
    completed = n["tp"] + n["fp"] + n["fn"] + n["tn"]
    if (n["completed"] != completed or n["attempts"] != completed + n["acquisition_errors"]
            + n["communication_errors"] + n["sensor_errors"] + n["unclassified"] or n["wrong_id"] > n["fn"]):
        raise ValueError("Summary counts/denominators disagree")
    if ((row["case"] == "genuine" and (n["fp"] or n["tn"]))
            or (row["case"] == "impostor" and (n["tp"] or n["fn"]))):
        raise ValueError("Confusion counts mixed between cases")
    rates = {
        "accuracy_pct": (n["tp"] + n["tn"], completed),
        "precision_pct": (n["tp"], n["tp"] + n["fp"]),
        "recall_pct": (n["tp"], n["tp"] + n["fn"]),
        "specificity_pct": (n["tn"], n["tn"] + n["fp"]),
        "fpr_pct": (n["fp"], n["fp"] + n["tn"]),
        "fnr_pct": (n["fn"], n["fn"] + n["tp"]),
        "coverage_pct": (completed, n["attempts"]),
    }
    for field, (numerator, denominator) in rates.items():
        if not denominator:
            if row[field] != "NA":
                raise ValueError("Undefined rate must be NA")
        else:
            value = float(row[field])
            if not math.isfinite(value) or abs(value - 100 * numerator / denominator) > 0.0002:
                raise ValueError(f"Incorrect rate: {field}")


class Capture:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.buffer = bytearray()
        self.latest = {}
        self.pending_summary = []
        self.complete_groups = 0
        self.snapshot_pending = self.snapshot_warned = False
        self.last_event = {}
        self.logged_attempts = {}
        self.trial_gaps = []
        self.issues = 0
        self.issue_file = None
        self.closed = False
        self.files = []
        self.trials = self.summaries = 0
        self.headers = set()
        self.clock_header_seen = False
        self.clock_offset = None
        self.pending_trial_times = set()
        try:
            self.console = self._open("console.log")
            self.trial_file = self._open("trials.csv")
            self.summary_file = self._open("summary-history.csv")
            self.issue_file = self._open("recording-issues.log")
            self.time_file = self._open("timestamps.csv")
            self.time_writer = csv.DictWriter(self.time_file, fieldnames=SAVED_TIME_FIELDS)
            self.time_writer.writeheader()
            self.trial_writer = csv.DictWriter(self.trial_file, fieldnames=TRIAL_FIELDS)
            self.summary_writer = csv.DictWriter(self.summary_file, fieldnames=SUMMARY_FIELDS)
            self.trial_writer.writeheader()
            self.summary_writer.writeheader()
        except BaseException:
            self.close()
            raise

    def _open(self, name):
        f = (self.directory / name).open("x", encoding="utf-8", newline="")
        self.files.append(f)
        return f

    @staticmethod
    def sync(file):
        file.flush()
        os.fsync(file.fileno())

    def issue(self, message):
        self.issues += 1
        print(f"Recorder notice: {message}", file=sys.stderr)
        if self.issue_file:
            self.issue_file.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
            self.sync(self.issue_file)

    def retry_snapshot(self):
        if not self.snapshot_pending:
            return
        path = self.directory / "latest-summary.csv"
        temporary = path.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
                writer.writeheader()
                writer.writerows(self.latest.values())
                self.sync(f)
            temporary.replace(path)
        except PermissionError:
            if not self.snapshot_warned:
                self.issue("Summary snapshot could not be replaced (access denied). Recording continues in trials.csv and summary-history.csv; retrying the snapshot.")
                self.snapshot_warned = True
            return
        self.snapshot_pending = self.snapshot_warned = False

    def accept_summary(self, row):
        pair = (row["source"], row["case"])
        if pair == SUMMARY_ORDER[0]:
            if self.pending_summary:
                self.issue("Previous summary group was incomplete; it was not published as latest.")
            self.pending_summary = []
        expected = SUMMARY_ORDER[len(self.pending_summary)]
        if pair != expected or (self.pending_summary and any(row[k] != self.pending_summary[0][k] for k in ("session", "test"))):
            self.issue("Incomplete/out-of-order summary group; awaiting all six rows before publishing.")
            self.pending_summary = []
            return
        self.pending_summary.append(row)
        if len(self.pending_summary) != 6:
            return
        rows = self.pending_summary
        for start in (0, 3):
            genuine, impostor, combined = rows[start:start + 3]
            for field in SUMMARY_FIELDS[4:16]:
                if int(combined[field]) != int(genuine[field]) + int(impostor[field]):
                    self.pending_summary = []
                    raise ValueError(f"Combined summary disagrees with its cases: {field}")
            for case in (genuine, impostor):
                key = tuple(case[k] for k in SUMMARY_FIELDS[:4])
                saved = self.logged_attempts.get(key, 0)
                if saved != int(case["attempts"]):
                    self.issue(f"{key}: firmware reports {case['attempts']} attempts but this trial CSV contains {saved}; earlier or lost trial rows are unavailable.")
        for complete in rows:
            self.latest[tuple(complete[k] for k in SUMMARY_FIELDS[:4])] = complete
        self.pending_summary = []
        self.complete_groups += 1
        self.snapshot_pending = True
        self.retry_snapshot()

    def feed(self, data: bytes):
        self.console.write(data.decode("ascii", errors="replace"))
        self.sync(self.console)  # Preserve diagnostics even if a CSV record is invalid.
        self.buffer.extend(data)
        while b"\n" in self.buffer:
            raw, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            if len(raw) > 8192:
                raise ValueError("Oversized console line; raw log retained")
            if self.last_event and any(b > 127 for b in raw):
                self.issue("Non-ASCII serial data during trial collection; inspect console.log for a corrupted record.")
            self.line(raw.rstrip(b"\r").decode("ascii", errors="replace"))
        if len(self.buffer) > 8192:
            raise ValueError("Oversized/incomplete console line; raw log retained")

    def line(self, text):
        if text.partition(",")[0] not in {"ACCHEADER", "ACCSUMMARYHEADER", "ACCTRIAL", "ACCSUMMARY", "ACCTIMEHEADER", "ACCTIME"}:
            return
        fields = next(csv.reader([text], strict=True)) if text else []
        if not fields:
            return
        tag = fields.pop(0)
        if tag == "ACCTIMEHEADER":
            if fields != TIME_FIELDS:
                raise ValueError("Firmware RTC schema differs; update recorder")
            self.clock_header_seen = True
            return
        if tag == "ACCTIME":
            if len(fields) != len(TIME_FIELDS):
                raise ValueError("Invalid RTC column count")
            row = timestamp_row(dict(zip(TIME_FIELDS, fields)))
            self.clock_offset = int(row["rtc_utc_offset_minutes"])
            if row["scope"] == "trial" and self.last_event.get((row["session"], row["test"])) != int(row["event_id"]):
                self.issue("RTC timestamp has no immediately corresponding recorded trial; inspect raw console.")
            self.pending_trial_times.discard((row["session"], row["test"], row["event_id"]))
            self.time_writer.writerow(row)
            self.sync(self.time_file)
            return
        if tag in {"ACCHEADER", "ACCSUMMARYHEADER"}:
            expected = TRIAL_FIELDS if tag == "ACCHEADER" else SUMMARY_FIELDS
            if fields != expected:
                raise ValueError("Firmware CSV schema differs; update the matching recorder")
            self.headers.add(tag)
        elif tag in {"ACCTRIAL", "ACCSUMMARY"}:
            names = TRIAL_FIELDS if tag == "ACCTRIAL" else SUMMARY_FIELDS
            if len(fields) != len(names):
                raise ValueError(f"Truncated/invalid {tag} column count")
            row = dict(zip(names, fields))
            if tag == "ACCTRIAL":
                validate_trial(row)
                key = (row["session"], row["test"])
                event = number(row["event_id"])
                previous = self.last_event.get(key, 0)
                if event <= previous:
                    raise ValueError("Duplicate or out-of-order trial ID; row not counted again")
                if event != previous + 1:
                    gap = (key, previous + 1, event - 1)
                    self.trial_gaps.append(gap)
                    self.issue(f"Missing trial events {gap[1]}..{gap[2]} for {key}; data was lost or capture began late.")
                self.trial_writer.writerow(row)
                self.sync(self.trial_file)
                self.trials += 1
                self.last_event[key] = event
                if self.clock_header_seen:
                    self.pending_trial_times.add((row["session"], row["test"], row["event_id"]))
                if row["counted"] == "1":
                    count_key = tuple(row[k] for k in SUMMARY_FIELDS[:4])
                    self.logged_attempts[count_key] = self.logged_attempts.get(count_key, 0) + 1
            else:
                validate_summary(row)
                self.summary_writer.writerow(row)
                self.sync(self.summary_file)
                self.summaries += 1
                self.accept_summary(row)

    def close(self):
        if self.closed:
            return
        try:
            if self.pending_summary:
                self.issue("Capture ended with an incomplete summary group; latest-summary.csv retains the previous complete snapshot.")
            if self.buffer and self.summaries:
                self.issue("Capture ended with an incomplete serial line; raw bytes retained in console.log.")
            if self.pending_trial_times:
                self.issue(f"Missing RTC timestamp rows for {len(self.pending_trial_times)} recorded trials; timestamps were not invented.")
            self.retry_snapshot()
        finally:
            self.closed = True
            for file in self.files:
                file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def keyboard():
    import msvcrt
    if not msvcrt.kbhit():
        return b""
    key = msvcrt.getwch()
    if key in {"\x00", "\xe0"}:
        msvcrt.getwch()
        return b""
    if key == "\x03":
        raise KeyboardInterrupt
    return ("\n" if key == "\r" else key).encode("ascii", errors="ignore")


def stop_and_collect(port, capture, read_once, ready, *, timeout=3):
    """Protect cleanup from repeated Ctrl+C; finish once six final rows arrive."""
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        if not ready:
            port.write(b"p\n")
            return
        before = capture.complete_groups
        port.write(b"p\ns\n")
        deadline = time.monotonic() + timeout
        while capture.complete_groups == before and time.monotonic() < deadline:
            read_once()
        if capture.complete_groups == before:
            print("Final summaries incomplete; keeping all records already saved.")
    finally:
        signal.signal(signal.SIGINT, previous)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM12")
    parser.add_argument("--out", type=Path, help="New output folder; existing folders are refused")
    parser.add_argument("--new-session", action="store_true", help="Pause and explicitly clear firmware RAM statistics")
    parser.add_argument("--sync-rtc", action="store_true", help="Explicitly set DS1307 from PC UTC using the configured local offset; starts a new firmware session")
    parser.add_argument("--rtc-offset-minutes", type=int, default=60, help="RTC local UTC offset; default +60 for Africa/Lagos; must match firmware")
    parser.add_argument("--no-input", action="store_true", help="Record only; don't forward Windows keyboard input")
    args = parser.parse_args(argv)
    if not -840 <= args.rtc_offset_minutes <= 840:
        parser.error("RTC offset must be between -840 and 840 minutes")
    if os.name != "nt" and not args.no_input:
        parser.error("Interactive keyboard forwarding is Windows-only; use --no-input elsewhere")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-UTC")
    output = args.out or Path(__file__).resolve().parents[3] / "private-data" / "fingerprint-accuracy" / f"run-{stamp}-{uuid.uuid4().hex[:8]}"
    try:
        import serial
        port = serial.Serial(port=None, baudrate=115200, timeout=0.05, write_timeout=2)
        port.dtr = port.rts = False
        port.port = args.port
        with Capture(output) as capture, port:
            print(f"Saving console/CSV to {output.resolve()}")
            print("Waiting for accuracy-firmware headers before enabling keyboard forwarding...")
            port.write(b"h\n")
            handshake_started = time.monotonic()
            retry_at = handshake_started
            requested_summary = ready = False
            clock_requested_at = None

            def read_once():
                data = port.read(max(1, min(port.in_waiting, 4096)))
                if data:
                    capture.feed(data)
                    sys.stdout.write(data.decode("ascii", errors="replace"))
                    sys.stdout.flush()

            try:
                while True:
                    read_once()
                    if len(capture.headers) == 2 and not requested_summary:
                        port.write(b"p\nn\ns\n" if args.new_session else b"s\n")
                        requested_summary = True
                    if requested_summary and capture.complete_groups and not ready:
                        sync_command = b""
                        if args.sync_rtc:
                            sync_command = rtc_sync_command(capture, args.rtc_offset_minutes)
                            if sync_command is None:
                                if clock_requested_at is None:
                                    port.write(b"z\n")
                                    clock_requested_at = time.monotonic()
                                    print("Requesting RTC status before checking its UTC offset...")
                                elif time.monotonic() - clock_requested_at > 5:
                                    raise ValueError("No RTC status reply to z; clock was not set. Raw log retained.")
                        if sync_command is not None:
                            if sync_command:
                                port.write(sync_command)
                            ready = True
                            print("\nRecorder ready. Keys: e enroll, t <ID> Enter, g/i, a/m, 1/2/3, q diagnostic, z RTC, w ticking check, s, p/r. Ctrl+C pauses and saves summaries.")
                    if not ready and time.monotonic() - handshake_started > 45:
                        raise ValueError("No accuracy-firmware handshake; upload the selected accuracy environment first")
                    if capture.snapshot_pending and time.monotonic() - retry_at >= 1:
                        retry_at = time.monotonic()
                        capture.retry_snapshot()
                    if ready and not args.no_input:
                        key = keyboard()
                        if key:
                            port.write(key)
                            sys.stdout.write(key.decode("ascii"))
                            sys.stdout.flush()
            except KeyboardInterrupt:
                print("\nPausing scanner and requesting final summaries...")
                stop_and_collect(port, capture, read_once, ready)
            finally:
                # Also stop new trials if disk/CSV/serial validation fails.
                try:
                    port.write(b"p\n")
                except Exception:
                    pass
            print(f"Saved {capture.trials} trial/observation rows and {capture.summaries} summary rows.")
            if capture.snapshot_pending:
                print("Latest snapshot replacement is still pending; read summary-history.csv and recording-issues.log.")
            else:
                print(f"Latest complete reported counts: {output.resolve() / 'latest-summary.csv'}")
            if capture.issues:
                print("Recording notices were reported; review recording-issues.log before treating the trial log as complete.")
            if not capture.complete_groups:
                raise ValueError("No complete accuracy summary received; raw log/history retained.")
    except Exception as error:
        print(f"Capture stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
