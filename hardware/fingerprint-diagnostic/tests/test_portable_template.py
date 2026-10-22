"""Synthetic records and serial transcripts; no hardware or real biometrics."""
import base64
from dataclasses import asdict, replace
import hashlib
import io
from contextlib import redirect_stdout, redirect_stderr
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import portable_template as fp

STUDENT = "11111111-1111-4111-8111-111111111111"
SCANNER = "22222222-2222-4222-8222-222222222222"
GALLERY = "33333333-3333-4333-8333-333333333333"
TEMPLATE = "44444444-4444-4444-8444-444444444444"
DATA = bytes(range(256)) + bytes(range(44))
PARAMETERS = dict(slot_id=1, capacity=150, security_level=3, packet_bytes=128,
                  system_id=0, device_address="FFFFFFFF")


class FakePort:
    def __init__(self, lines):
        self.lines = list(lines)
        self.writes = []

    def readline(self, _limit):
        return self.lines.pop(0) if self.lines else b""

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        pass


def record():
    return fp.FingerprintTemplateRecord.create(
        DATA, student_id=STUDENT, finger_label="right_index", scanner_id=SCANNER,
        gallery_id=GALLERY, compatibility_group="as608-unit-1", parameters=PARAMETERS,
        template_id=TEMPLATE,
    )


def transcript(slot=1):
    lines = [b"unrelated report line\n", f"FPBEGIN 1 {slot} 150 3 128 0 FFFFFFFF\n".encode()]
    lines.extend(("FPDATA " + DATA[i:i + 32].hex() + "\n").encode()
                 for i in range(0, len(DATA), 32))
    lines.append(f"FPEND {len(DATA)} {zlib.crc32(DATA):08X}\n".encode())
    return lines


class PortableTemplateTests(unittest.TestCase):
    def test_console_line_can_arrive_in_multiple_reads(self):
        port = FakePort([b"FPREA", b"", b"DY 2 ", b"300\r\n"])
        self.assertEqual(fp.read_line(port, time.monotonic() + 1), "FPREADY 2 300")
        with self.assertRaises(ValueError):
            fp.read_line(FakePort([b"X" * 256]), time.monotonic() + 1)

    def test_record_round_trip_and_stable_identity(self):
        original = record()
        restored = fp.FingerprintTemplateRecord(**json.loads(json.dumps(asdict(original))))
        self.assertEqual(restored.validated_bytes(), DATA)
        self.assertEqual(restored.template_id, TEMPLATE)
        self.assertEqual(restored.student_id, STUDENT)
        self.assertEqual(restored.source["slot_id"], 1)
        self.assertEqual(restored.template_sha256, hashlib.sha256(DATA).hexdigest())

    def test_invalid_records_are_rejected(self):
        for changes in (
            dict(schema_version=True), dict(schema_version=3), dict(student_id="1"),
            dict(template_id="00000000-0000-0000-0000-000000000000"),
            dict(template_format="unknown"), dict(byte_length=299),
            dict(template_sha256="0" * 64), dict(template_base64="invalid@"),
            dict(template_base64=base64.b64encode(b"X" * 2049).decode()),
            dict(finger_label="right index"), dict(compatibility_group=""),
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(record(), **changes).validated_bytes()

    def test_file_bounds_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.fpt.json"
            with path.open("x", encoding="utf-8") as stream:
                fp.write_json(stream, asdict(record()))
            self.assertEqual(fp.read_record(path).validated_bytes(), DATA)
            with self.assertRaises(FileExistsError):
                path.open("x", encoding="utf-8")
            path.write_text(" " * 16385)
            with self.assertRaises(ValueError):
                fp.read_record(path)

    def test_export_transcript(self):
        data, parameters = fp.receive_export(FakePort(transcript()), deadline=time.monotonic() + 1)
        self.assertEqual(data, DATA)
        self.assertEqual(parameters, PARAMETERS)

    def test_startup_noise_is_skipped_but_template_noise_is_rejected(self):
        lines = [b"\xffstartup noise\n"] + transcript()
        data, _ = fp.receive_export(FakePort(lines), deadline=time.monotonic() + 1)
        self.assertEqual(data, DATA)
        lines = transcript()
        lines[2] = b"FPDATA 00\xff11\n"
        with self.assertRaises(ValueError):
            fp.receive_export(FakePort(lines), deadline=time.monotonic() + 1)

    def test_export_corruption_and_partial_data(self):
        variants = []
        lines = transcript(); lines[-1] = b"FPEND 300 00000000\n"; variants.append(lines)
        lines = transcript(); lines[2] = b"FPDATA GG\n"; variants.append(lines)
        lines = transcript(); lines[-1] = b"FPEND 299 00000000\n"; variants.append(lines)
        lines = transcript(); lines[-1] = b"FPERROR timeout\n"; variants.append(lines)
        lines = transcript(); lines[1] = b"FPBEGIN 2 1 150 3 128 0 FFFFFFFF\n"; variants.append(lines)
        lines = transcript(); lines[2] = b"FPDATA 0"; variants.append(lines)
        lines = [b"FPBEGIN 1 1 150 3 128 0 FFFFFFFF\n"] + [b"FPDATA " + b"00" * 32 + b"\n"] * 65
        variants.append(lines)
        for lines in variants:
            with self.subTest(lines=lines[-1]), self.assertRaises(ValueError):
                fp.receive_export(FakePort(lines), deadline=time.monotonic() + 1)

    @patch.object(fp.time, "sleep")
    def test_restore_receipt_and_sent_bytes(self, _sleep):
        checksum = zlib.crc32(DATA)
        port = FakePort([b"FPREADY 2 300\n", f"FPSTORED 2 300 {checksum:08X}\n".encode()])
        planned = []
        slot = fp.restore_bytes(port, DATA, deadline=time.monotonic() + 1, on_ready=planned.append)
        self.assertEqual(planned, [2])
        self.assertEqual(slot, 2)
        self.assertEqual(port.writes[0], f"u 300 {checksum:08X}\n".encode())
        self.assertEqual(bytes.fromhex(b"".join(port.writes[1:]).decode()), DATA)

    @patch.object(fp.time, "sleep")
    def test_restore_failure_has_no_verified_result(self, _sleep):
        for lines in ([b"FPERROR full\n"], [b"FPREADY 2 299\n"],
                      [b"FPREADY 2 300\n", b"FPERROR checksum\n"],
                      [b"FPREADY 2 300\n", b"FPSTORED 3 300 00000000\n"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                fp.restore_bytes(FakePort(lines), DATA, deadline=time.monotonic() + 1)

    def test_pending_receipt_remains_when_restore_fails(self):
        # The CLI creates/fsyncs pending metadata before connection/mutation.
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "synthetic.fpt.json"
            package.write_text(json.dumps(asdict(record())))
            receipt = Path(folder) / "pending.receipt.json"
            argv = ["portable_template.py", "restore", "--port", "FAKE", "--record", str(package),
                    "--target-scanner-id", SCANNER, "--target-gallery-id", GALLERY,
                    "--compatibility-group", "as608-unit-1", "--receipt", str(receipt)]
            with patch.object(sys, "argv", argv), patch.object(fp, "connect", side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    fp.main()
            self.assertEqual(json.loads(receipt.read_text())["status"], "pending")
            self.assertEqual(json.loads(receipt.read_text())["template_id"], TEMPLATE)

    def test_incompatible_group_stops_before_connection(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "synthetic.fpt.json"
            package.write_text(json.dumps(asdict(record())))
            argv = ["portable_template.py", "restore", "--port", "FAKE", "--record", str(package),
                    "--target-scanner-id", SCANNER, "--target-gallery-id", GALLERY,
                    "--compatibility-group", "other", "--receipt", str(Path(folder) / "receipt.json")]
            with patch.object(sys, "argv", argv), patch.object(fp, "connect") as connect:
                with self.assertRaises(ValueError):
                    fp.main()
                connect.assert_not_called()

    def test_unassigned_v2_records_and_legacy_v1(self):
        self.assertEqual(replace(record(), student_id=None).validated_bytes(), DATA)
        self.assertEqual(replace(record(), schema_version=1).validated_bytes(), DATA)
        with self.assertRaises((TypeError, ValueError)):
            replace(record(), schema_version=1, student_id=None).validated_bytes()

    def test_sparse_inventory_and_selection(self):
        lines = [b"FPSTEP Reading index\n", b"FPLISTBEGIN 1 600 3\n",
                 b"FPSLOT 1\n", b"FPSLOT 257\n", b"FPSLOT 599\n", b"FPLISTEND 3\n"]
        port = FakePort(lines)
        slots, capacity = fp.read_inventory(port)
        self.assertEqual((slots, capacity), ([1, 257, 599], 600))
        self.assertEqual(port.writes, [b"l\n"])
        self.assertEqual(fp.parse_selection("ALL", slots), slots)
        self.assertEqual(fp.parse_selection("599, 1,599", slots), [599, 1])
        for text in ("", "2", "-1", "1,", "1-599", "1,2"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                fp.parse_selection(text, slots)
        self.assertEqual(fp.read_inventory(FakePort([b"FPLISTBEGIN 1 150 0\n", b"FPLISTEND 0\n"])), ([], 150))

    def test_inventory_rejects_duplicates_bounds_and_partial_lists(self):
        for lines in (
            [b"FPLISTBEGIN 1 150 2\n", b"FPSLOT 1\n", b"FPSLOT 1\n"],
            [b"FPLISTBEGIN 1 150 1\n", b"FPSLOT 150\n"],
            [b"FPLISTBEGIN 1 150 2\n", b"FPSLOT 1\n", b"FPLISTEND 2\n"],
            [b"FPLISTBEGIN 1 150 1\n", b"FPERROR index failed\n"],
        ):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                fp.read_inventory(FakePort(lines))

    def test_bulk_exports_have_files_manifest_unassigned_owners_and_feedback(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()) as output:
            root = Path(folder)
            profile, profile_path = fp.export_profile(root)
            port = FakePort(transcript(1) + transcript(7))
            manifest = fp.run_exports(port, [1, 7], root=root, profile=profile, profile_path=profile_path)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(port.writes, [b"t 1\n", b"t 7\n"])
            self.assertEqual(len(manifest["exports"]), 2)
            saved = [fp.read_record(Path(item["path"])) for item in manifest["exports"]]
            self.assertTrue(all(item.student_id is None and item.validated_bytes() == DATA for item in saved))
            # Exact byte duplicates preserve template UUID without inventing a person identity.
            self.assertEqual(saved[0].template_id, saved[1].template_id)
            self.assertIn("[SUMMARY] 2/2 files verified", output.getvalue())
            self.assertEqual(output.getvalue().count("[SAVED]"), 2)
            self.assertNotIn("FPDATA", output.getvalue())
            self.assertNotIn(base64.b64encode(DATA).decode(), output.getvalue())
            again = fp.run_exports(FakePort(transcript(1)), [1], root=root, profile=profile,
                                   profile_path=profile_path)
            self.assertEqual(again["exports"][0]["template_id"], saved[0].template_id)
            self.assertNotEqual(again["exports"][0]["path"], manifest["exports"][0]["path"])

    def test_bulk_failure_keeps_verified_files_and_marks_remaining(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder)
            profile, profile_path = fp.export_profile(root)
            bad = transcript(7)
            bad[-1] = b"FPEND 300 00000000\n"
            port = FakePort(transcript(1) + bad)
            manifest = fp.run_exports(port, [1, 7, 9], root=root, profile=profile, profile_path=profile_path)
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(manifest["failures"][0]["slot_id"], 7)
            self.assertEqual(manifest["unattempted_slots"], [9])
            self.assertEqual(len(manifest["exports"]), 1)
            self.assertEqual(fp.read_record(Path(manifest["exports"][0]["path"])).validated_bytes(), DATA)
            self.assertNotIn(b"t 9\n", port.writes)
            path = next(root.glob("export-*/manifest.json"))
            self.assertEqual(json.loads(path.read_text())["status"], "partial")

    def test_device_error_feedback_keeps_reason_but_not_payload(self):
        port = FakePort([b"FPDATA private-bytes\n", b"ReadSysPara: timeout\n", b"FPERROR stop\n"])
        with self.assertRaisesRegex(ValueError, "ReadSysPara: timeout") as caught:
            fp.wait_marker(port, "FPBEGIN ", time.monotonic() + 1)
        self.assertNotIn("private-bytes", str(caught.exception))

    def test_bulk_save_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()) as output:
            root = Path(folder)
            profile, profile_path = fp.export_profile(root)
            original_save = fp.save_json_file

            def fail_second_file(path, value, **kwargs):
                if path.name == "slot-00007.fpt.json": raise OSError("simulated disk full")
                return original_save(path, value, **kwargs)

            with patch.object(fp, "save_json_file", side_effect=fail_second_file):
                manifest = fp.run_exports(FakePort(transcript(1) + transcript(7)), [1, 7],
                                         root=root, profile=profile, profile_path=profile_path)
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(len(manifest["exports"]), 1)
            self.assertEqual(manifest["failures"][0]["slot_id"], 7)
            self.assertIn("simulated disk full", output.getvalue())
            self.assertEqual(output.getvalue().count("[SAVED]"), 1)

    def test_menu_selects_all_and_quits(self):
        class MenuPort(FakePort):
            def __enter__(self): return self
            def __exit__(self, *_args): pass

        inventory = [b"FPLISTBEGIN 1 150 1\n", b"FPSLOT 1\n", b"FPLISTEND 1\n"]
        port = MenuPort(inventory + transcript(1) + inventory)
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()) as output:
            argv = ["portable_template.py", "menu", "--port", "FAKE", "--out-dir", folder]
            with patch.object(sys, "argv", argv), patch.object(fp, "connect", return_value=port), \
                    patch("builtins.input", side_effect=["bad", "ALL", "Q"]):
                self.assertEqual(fp.main(), 0)
            self.assertIn("Available IDs: 1", output.getvalue())
            self.assertIn("serial port released", output.getvalue())
            self.assertEqual(port.writes, [b"l\n", b"t 1\n", b"l\n"])

    def test_bulk_identity_override_is_rejected_before_connecting(self):
        argv = ["portable_template.py", "export", "--port", "FAKE", "--all", "--student-id", STUDENT]
        with patch.object(sys, "argv", argv), patch.object(fp, "connect") as connect, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): fp.main()
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
