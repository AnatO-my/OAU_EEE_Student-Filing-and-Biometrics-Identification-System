"""Transfer opaque EF01 templates through the ESP32 USB serial console.

No database/network writes. Real template files belong in private storage.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

FORMAT = "as608-ef01-opaque"
MAX_BYTES = 2048
HEX_LINE = re.compile(r"[0-9A-Fa-f]{2,64}\Z")
DEFAULT_EXPORT_ROOT = Path(__file__).resolve().parents[3] / "private-data" / "fingerprint-templates"


def canonical_uuid(value: str) -> str:
    parsed = uuid.UUID(value)
    if parsed.int == 0:
        raise ValueError("Use a nonzero UUID")
    return str(parsed)


def label(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
        raise ValueError("Labels must contain 1–80 letters, digits, _, . or -")
    return value


@dataclass(frozen=True)
class FingerprintTemplateRecord:
    schema_version: int
    template_id: str
    student_id: str | None
    finger_label: str
    template_format: str
    compatibility_group: str
    byte_length: int
    template_sha256: str
    template_base64: str
    exported_at: str
    source: dict

    @classmethod
    def create(cls, data: bytes, *, student_id: str | None, finger_label: str,
               scanner_id: str, gallery_id: str, compatibility_group: str,
               parameters: dict, template_id: str | None = None):
        if not 1 <= len(data) <= MAX_BYTES:
            raise ValueError("Template size is outside the 1–2048 byte transfer limit")
        return cls(
            schema_version=2,
            template_id=canonical_uuid(template_id or str(uuid.uuid4())),
            student_id=canonical_uuid(student_id) if student_id else None,
            finger_label=label(finger_label),
            template_format=FORMAT,
            compatibility_group=label(compatibility_group),
            byte_length=len(data),
            template_sha256=hashlib.sha256(data).hexdigest(),
            template_base64=base64.b64encode(data).decode("ascii"),
            exported_at=datetime.now(timezone.utc).isoformat(),
            source={**parameters, "scanner_id": canonical_uuid(scanner_id),
                    "gallery_id": canonical_uuid(gallery_id),
                    "model_label": "AS608 (user supplied)", "firmware_version": None},
        )

    def validated_bytes(self) -> bytes:
        if type(self.schema_version) is not int or self.schema_version not in (1, 2):
            raise ValueError("Unsupported record schema version")
        if self.template_format != FORMAT:
            raise ValueError("Unsupported template format")
        canonical_uuid(self.template_id)
        if self.schema_version == 1 or self.student_id is not None:
            canonical_uuid(self.student_id)
        label(self.finger_label)
        label(self.compatibility_group)
        if type(self.byte_length) is not int or not 1 <= self.byte_length <= MAX_BYTES:
            raise ValueError("Invalid template byte length")
        if not isinstance(self.template_base64, str) or len(self.template_base64) > 4 * ((MAX_BYTES + 2) // 3):
            raise ValueError("Invalid/oversized Base64 template")
        data = base64.b64decode(self.template_base64, validate=True)
        if len(data) != self.byte_length:
            raise ValueError("Template byte count disagrees with the record")
        if hashlib.sha256(data).hexdigest() != self.template_sha256:
            raise ValueError("Template SHA-256 checksum mismatch")
        if not isinstance(self.source, dict):
            raise ValueError("Invalid source metadata")
        canonical_uuid(self.source["scanner_id"])
        canonical_uuid(self.source["gallery_id"])
        validate_parameters(self.source)
        datetime.fromisoformat(self.exported_at)
        return data


def validate_parameters(parameters: dict):
    for name, minimum, maximum in (
        ("capacity", 1, 65535), ("slot_id", 0, 65534),
        ("security_level", 0, 65535), ("system_id", 0, 65535),
    ):
        value = parameters[name]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"Invalid source {name}")
    if parameters["slot_id"] >= parameters["capacity"]:
        raise ValueError("Source slot exceeds capacity")
    if parameters["packet_bytes"] not in (32, 64, 128, 256):
        raise ValueError("Invalid source packet size")
    if not re.fullmatch(r"[0-9A-F]{8}", parameters["device_address"]):
        raise ValueError("Invalid source device address")


def read_record(path: Path) -> FingerprintTemplateRecord:
    if path.stat().st_size > 16384:
        raise ValueError("Record file exceeds the 16 KiB input limit")
    record = FingerprintTemplateRecord(**json.loads(path.read_text(encoding="utf-8")))
    record.validated_bytes()
    return record


def read_line(port, deadline: float) -> str:
    buffered = bytearray()
    while time.monotonic() < deadline:
        raw = port.readline(256 - len(buffered))
        if not raw:
            continue
        buffered.extend(raw)
        if len(buffered) >= 256:
            raise ValueError("Oversized console line; transfer stopped")
        if buffered.endswith(b"\n"):
            # Startup/reset noise is not a valid protocol marker. Preserve it
            # as replacement characters so marker waits can continue; any
            # damaged FPDATA line still fails strict hex/CRC validation.
            return buffered.decode("ascii", errors="replace").strip()
    raise TimeoutError("ESP32 response timeout; check monitor is closed and firmware is current")


def wait_marker(port, marker: str, deadline: float, on_status=None) -> str:
    recent = []
    while True:
        line = read_line(port, deadline)
        if line.startswith("FPERROR"):
            detail = "; ".join(recent[-3:])
            raise ValueError("ESP32 stopped the operation" + (f": {detail}" if detail else ""))
        if line.startswith(marker):
            return line
        if line.startswith("FPSTEP "):
            if on_status: on_status(line[7:])
        elif on_status and line.startswith(("Lift your finger", "Place a finger", "Finger removed.")):
            on_status(line)
        elif line.startswith(("GenImg:", "Img2Tz:", "No finger detected", "Capture cancelled", "ReadSysPara:", "TemplateNum:", "ReadIndexTable:",
                              "LoadChar:", "UpChar:", "Cannot export:", "No authenticated",
                              "Template transfer", "Truncated template", "Invalid template",
                              "Template exceeds", "Stored count", "Unsupported data")):
            recent.append(line[:180])
            recent = recent[-3:]


def receive_export(port, *, deadline: float, on_status=None):
    header = wait_marker(port, "FPBEGIN ", deadline, on_status).split()
    if len(header) != 8 or header[1] != "1":
        raise ValueError("Invalid export header/version")
    parameters = dict(zip(
        ("slot_id", "capacity", "security_level", "packet_bytes", "system_id"),
        map(int, header[2:7]),
    ))
    parameters["device_address"] = header[7]
    validate_parameters(parameters)
    data = bytearray()
    while True:
        line = read_line(port, deadline)
        if line.startswith("FPDATA "):
            encoded = line[7:]
            if not HEX_LINE.fullmatch(encoded) or len(encoded) % 2:
                raise ValueError("Malformed hex template line")
            data.extend(bytes.fromhex(encoded))
            if len(data) > MAX_BYTES:
                raise ValueError("Export exceeds the transfer limit")
        elif line.startswith("FPEND "):
            fields = line.split()
            if (len(fields) != 3 or not data or int(fields[1]) != len(data)
                    or not re.fullmatch(r"[0-9A-Fa-f]{8}", fields[2])
                    or int(fields[2], 16) != zlib.crc32(data)):
                raise ValueError("Export byte count/CRC mismatch")
            return bytes(data), parameters
        else:
            raise ValueError("Unexpected line inside template export")


def restore_bytes(port, data: bytes, *, deadline: float, on_ready=None) -> int:
    if not 1 <= len(data) <= MAX_BYTES:
        raise ValueError("Invalid restore size")
    checksum = zlib.crc32(data)
    port.write(f"u {len(data)} {checksum:08X}\n".encode("ascii"))
    ready = wait_marker(port, "FPREADY ", deadline).split()
    if len(ready) != 3 or int(ready[2]) != len(data) or not 0 <= int(ready[1]) <= 65534:
        raise ValueError("Invalid restore handshake")
    slot = int(ready[1])
    if on_ready is not None:
        on_ready(slot)  # Persist the planned binding before sending template data.
    for offset in range(0, len(data), 32):
        port.write((data[offset:offset + 32].hex() + "\n").encode("ascii"))
        # Keep the conventional ESP32 UART0 RX buffer from being flooded.
        port.flush()
        time.sleep(0.02)
    expected = f"FPSTORED {slot} {len(data)} {checksum:08X}"
    receipt = wait_marker(port, "FPSTORED ", deadline)
    if receipt != expected:
        raise ValueError("Restore receipt disagrees with requested bytes/slot")
    return slot


def connect(port_name: str, on_status=None):
    import serial  # Included in PlatformIO's Python environment; otherwise pip install pyserial.

    if on_status: on_status(f"Opening {port_name} at 115200 baud; keep Serial Monitor closed")
    port = serial.Serial(port=None, baudrate=115200, timeout=1, write_timeout=5)
    port.dtr = False
    port.rts = False
    port.port = port_name
    port.open()
    try:
        time.sleep(2)
        port.reset_input_buffer()
        port.write(b"h\n")
        wait_marker(port, "t <ID>", time.monotonic() + 45)
        if on_status: on_status("ESP32 console connected; export command available")
        return port
    except Exception:
        port.close()
        raise


def write_json(stream, value: dict):
    stream.seek(0)
    json.dump(value, stream, indent=2)
    stream.write("\n")
    stream.truncate()
    stream.flush()
    os.fsync(stream.fileno())


def show_step(message):
    print(f"[STEP] {message}", flush=True)


def read_inventory(port, on_status=None):
    if on_status: on_status("Listing occupied scanner slots")
    port.write(b"l\n")
    deadline = time.monotonic() + 15
    try:
        header = wait_marker(port, "FPLISTBEGIN ", deadline, on_status).split()
    except TimeoutError as error:
        raise TimeoutError("No slot list received. Upload the updated firmware with the l command; "
                           "check scanner wiring and close other serial apps.") from error
    if len(header) != 4 or header[1] != "1":
        raise ValueError("Invalid slot-list header")
    capacity, stored = map(int, header[2:])
    if not 1 <= capacity <= 65535 or not 0 <= stored <= capacity:
        raise ValueError("Invalid library size/count")
    slots = []
    seen = set()
    while True:
        line = read_line(port, deadline)
        fields = line.split()
        if len(fields) == 2 and fields[0] == "FPSLOT":
            slot = int(fields[1])
            if slot < 0 or slot >= capacity or slot in seen or len(slots) >= stored:
                raise ValueError("Invalid/duplicate occupied slot")
            seen.add(slot)
            slots.append(slot)
        elif len(fields) == 2 and fields[0] == "FPLISTEND":
            if int(fields[1]) != stored or len(slots) != stored:
                raise ValueError("Incomplete slot list; export stopped")
            return sorted(slots), capacity
        else:
            raise ValueError("Invalid/incomplete slot list; export stopped")


def parse_selection(text, available):
    if text.strip().lower() == "all":
        return list(available)
    fields = text.split(",")
    if not fields or any(not re.fullmatch(r"\s*\d+\s*", value) for value in fields):
        raise ValueError("Enter an occupied slot ID, comma-separated IDs, or ALL")
    slots = list(dict.fromkeys(int(value) for value in fields))
    missing = [slot for slot in slots if slot not in available]
    if missing:
        raise ValueError("Not occupied: " + ", ".join(map(str, missing)))
    return slots


def save_json_file(path, value, *, create=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if create:
        with path.open("x", encoding="utf-8") as stream:
            write_json(stream, value)
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        write_json(stream, value)
    os.replace(temporary, path)


def export_profile(root, *, new_gallery=False):
    path = root / "export-profile.json"
    if path.exists():
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Export profile exceeds 4 MiB")
        profile = json.loads(path.read_text(encoding="utf-8"))
        if profile.get("schema_version") != 1 or not isinstance(profile.get("templates"), dict):
            raise ValueError("Unsupported export profile")
    else:
        # Reuse commissioning IDs from this project's earlier physical test,
        # when present. Never copy its test student identity into bulk exports.
        old_path = root / "slot10-test-session.json"
        old = json.loads(old_path.read_text(encoding="utf-8-sig")) if old_path.exists() else {}
        profile = {"schema_version": 1,
                   "scanner_id": old.get("scanner_id", str(uuid.uuid4())),
                   "gallery_id": old.get("gallery_id", str(uuid.uuid4())),
                   "compatibility_group": old.get("compatibility_group", "as608-unit-1"),
                   "templates": {}}
    canonical_uuid(profile["scanner_id"])
    canonical_uuid(profile["gallery_id"])
    label(profile["compatibility_group"])
    if new_gallery: profile["gallery_id"] = str(uuid.uuid4())
    save_json_file(path, profile)
    return profile, path


def run_exports(port, slots, *, root, profile, profile_path, student_id=None,
                finger_label=None, template_id=None, single_out=None):
    if len(slots) != 1 and (student_id is not None or finger_label is not None or template_id is not None):
        raise ValueError("Identity/finger/template overrides require one selected slot")
    if single_out is not None and (len(slots) != 1 or single_out.exists()):
        raise ValueError("Choose one slot and a new output filename")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder = root / f"export-{stamp}-{uuid.uuid4().hex[:8]}"
    folder.mkdir(parents=True, exist_ok=False)
    manifest_path = folder / "manifest.json"
    manifest = {"schema_version": 1, "status": "in_progress",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "scanner_id": profile["scanner_id"], "gallery_id": profile["gallery_id"],
                "selected_slots": slots, "exports": [], "failures": [], "unattempted_slots": []}
    save_json_file(manifest_path, manifest, create=True)
    print(f"[OK] Selected {len(slots)} template(s). Destination: {folder.resolve()}", flush=True)
    for index, slot in enumerate(slots):
        try:
            show_step(f"[{index + 1}/{len(slots)}] Exporting slot {slot}")
            port.write(f"t {slot}\n".encode("ascii"))
            data, parameters = receive_export(port, deadline=time.monotonic() + 30, on_status=show_step)
            if parameters["slot_id"] != slot:
                raise ValueError("Scanner returned a different slot")
            print(f"[OK] Slot {slot}: {len(data)} bytes received; transfer CRC verified", flush=True)
            digest = hashlib.sha256(data).hexdigest()
            key = profile["gallery_id"] + ":" + digest
            previous = profile["templates"].get(key, {})
            previous_owner = previous.get("student_id")
            if student_id and previous_owner and student_id != previous_owner:
                raise ValueError("This identical template already has a different student binding")
            record = FingerprintTemplateRecord.create(
                data, student_id=student_id or previous_owner,
                finger_label=finger_label or previous.get("finger_label", "unknown"),
                scanner_id=profile["scanner_id"], gallery_id=profile["gallery_id"],
                compatibility_group=profile["compatibility_group"], parameters=parameters,
                template_id=template_id or previous.get("template_id"),
            )
            record.validated_bytes()
            target = single_out if single_out is not None else folder / f"slot-{slot:05d}.fpt.json"
            show_step(f"Slot {slot}: saving portable JSON record")
            save_json_file(target, asdict(record), create=True)
            saved = read_record(target)
            if saved.validated_bytes() != data or saved.template_id != record.template_id:
                raise ValueError("Saved file readback validation failed")
            manifest["exports"].append({"slot_id": slot, "path": str(target.resolve()),
                "byte_length": len(data), "template_id": record.template_id,
                "student_id": record.student_id, "template_sha256": digest, "status": "verified"})
            profile["templates"][key] = {"template_id": record.template_id,
                "student_id": record.student_id, "finger_label": record.finger_label}
            save_json_file(manifest_path, manifest)
            save_json_file(profile_path, profile)
            print(f"[OK] Slot {slot}: file reopened and SHA-256 verified", flush=True)
            print(f"[SAVED] {target.resolve()}", flush=True)
        except (ValueError, KeyError, TypeError, OSError, TimeoutError) as error:
            manifest["failures"].append({"slot_id": slot, "error": str(error)})
            manifest["unattempted_slots"] = slots[index + 1:]
            manifest["status"] = "partial" if manifest["exports"] else "failed"
            print(f"[ERROR] Slot {slot}: {error}", flush=True)
            print("[STOPPED] Earlier verified files are retained; remaining slots were not attempted.", flush=True)
            break
    else:
        manifest["status"] = "complete"
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    save_json_file(manifest_path, manifest)
    print(f"[SUMMARY] {len(manifest['exports'])}/{len(slots)} files verified; "
          f"{len(manifest['failures'])} failed; {len(manifest['unattempted_slots'])} not attempted", flush=True)
    print(f"[MANIFEST] {manifest_path.resolve()}", flush=True)
    return manifest


def show_inventory(slots, capacity):
    print(f"[OK] Library: {len(slots)} occupied / {capacity} slots", flush=True)
    print("Available IDs: " + (", ".join(map(str, slots)) if slots else "none"), flush=True)


def export_menu(args):
    profile, profile_path = export_profile(args.out_dir, new_gallery=args.new_gallery)
    print("Fingerprint export menu. Exports do not erase sensor templates.", flush=True)
    print("Records have unassigned student identity unless previously bound explicitly.", flush=True)
    with connect(args.port, on_status=show_step) as port:
        slots, capacity = read_inventory(port, show_step)
        while True:
            show_inventory(slots, capacity)
            try:
                selection = input("Choose ID(s), ALL, R to refresh, or Q to quit: ").strip()
            except EOFError:
                return 0
            if selection.lower() in ("q", "quit", "exit"):
                print("[OK] Export menu closed; serial port released.")
                return 0
            if selection.lower() == "r":
                slots, capacity = read_inventory(port, show_step)
                continue
            try:
                chosen = parse_selection(selection, slots)
                if not chosen:
                    print("[OK] Library is empty; there is nothing to export.")
                    continue
            except ValueError as error:
                print(f"[ERROR] {error}")
                continue
            result = run_exports(port, chosen, root=args.out_dir, profile=profile,
                                 profile_path=profile_path)
            if result["status"] != "complete": return 1
            slots, capacity = read_inventory(port, show_step)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    menu = sub.add_parser("menu", help="List slots, select IDs or ALL, and save verified exports")
    menu.add_argument("--port", required=True)
    menu.add_argument("--out-dir", type=Path, default=DEFAULT_EXPORT_ROOT)
    menu.add_argument("--new-gallery", action="store_true", help="Use after a full sensor-library erase")
    listing = sub.add_parser("list", help="List actual occupied scanner slots")
    listing.add_argument("--port", required=True)
    export = sub.add_parser("export", help="Read an enrolled scanner slot to a private JSON record")
    export.add_argument("--port", required=True)
    targets = export.add_mutually_exclusive_group(required=True)
    targets.add_argument("--slot", type=int)
    targets.add_argument("--all", action="store_true", help="Export every occupied slot")
    export.add_argument("--student-id", type=canonical_uuid)
    export.add_argument("--finger", type=label)
    export.add_argument("--scanner-id", type=canonical_uuid)
    export.add_argument("--gallery-id", type=canonical_uuid)
    export.add_argument("--compatibility-group", type=label)
    export.add_argument("--template-id", type=canonical_uuid)
    export.add_argument("--out", type=Path, help="Optional new filename for one slot")
    export.add_argument("--out-dir", type=Path, default=DEFAULT_EXPORT_ROOT)
    export.add_argument("--new-gallery", action="store_true", help="Use after a full sensor-library erase")
    restore = sub.add_parser("restore", help="Write a validated record to a free scanner slot")
    restore.add_argument("--port", required=True)
    restore.add_argument("--record", required=True, type=Path)
    restore.add_argument("--target-scanner-id", required=True, type=canonical_uuid)
    restore.add_argument("--target-gallery-id", required=True, type=canonical_uuid)
    restore.add_argument("--compatibility-group", required=True, type=label)
    restore.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "menu":
        return export_menu(args)
    if args.command == "list":
        with connect(args.port, on_status=show_step) as port:
            slots, capacity = read_inventory(port, show_step)
            show_inventory(slots, capacity)
        return 0
    if args.command == "export":
        if args.slot is not None and not 0 <= args.slot <= 65534:
            parser.error("--slot must be in 0–65534 and within your scanner's capacity")
        if args.all and any(value is not None for value in (args.out, args.student_id, args.finger, args.template_id)):
            parser.error("--all uses separate files and per-template identity; omit --out and identity overrides")
        if args.out is not None and args.out.exists():
            parser.error("Output exists; choose a new path")
        profile, profile_path = export_profile(args.out_dir, new_gallery=args.new_gallery)
        for name in ("scanner_id", "gallery_id", "compatibility_group"):
            value = getattr(args, name)
            if value is not None: profile[name] = value
        with connect(args.port, on_status=show_step) as port:
            slots, capacity = read_inventory(port, show_step)
            show_inventory(slots, capacity)
            selected = slots if args.all else parse_selection(str(args.slot), slots)
            result = run_exports(port, selected, root=args.out_dir, profile=profile,
                profile_path=profile_path, student_id=args.student_id, finger_label=args.finger,
                template_id=args.template_id, single_out=args.out)
        return 0 if result["status"] == "complete" else 1
    else:
        show_step("Validating restore record and SHA-256")
        record = read_record(args.record)
        if record.compatibility_group != args.compatibility_group:
            raise ValueError("Compatibility group differs; no scanner write attempted")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema_version": 1, "status": "pending", "template_id": record.template_id,
            "student_id": record.student_id, "finger_label": record.finger_label,
            "scanner_id": args.target_scanner_id, "gallery_id": args.target_gallery_id,
            "slot_id": None, "template_sha256": record.template_sha256,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        # Reserve a durable receipt before any mutation. Failure leaves a pending
        # receipt for reconciliation, rather than claiming a successful binding.
        with args.receipt.open("x+", encoding="utf-8") as stream:
            write_json(stream, receipt)
            with connect(args.port) as port:
                def save_planned_slot(planned_slot):
                    receipt["slot_id"] = planned_slot
                    write_json(stream, receipt)

                slot = restore_bytes(port, record.validated_bytes(),
                                     deadline=time.monotonic() + 30, on_ready=save_planned_slot)
            receipt.update(status="verified", slot_id=slot,
                           verified_at=datetime.now(timezone.utc).isoformat())
            write_json(stream, receipt)
        print(f"Restored and read back exactly. New scanner slot: {slot}")
        print(f"Binding receipt: {args.receipt.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("\nStopped by user; serial port released. Check any in-progress manifest/receipt before retrying.")
    except (ValueError, KeyError, TypeError, OSError, TimeoutError) as error:
        raise SystemExit(f"Transfer failed: {error}")
