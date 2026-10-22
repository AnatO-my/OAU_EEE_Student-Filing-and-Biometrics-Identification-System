"""Single-capture export and later AS608-assisted comparison; no database writes."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

from portable_template import (MAX_BYTES, HEX_LINE, canonical_uuid, label, read_line,
                               wait_marker, connect, write_json, validate_parameters)

PROBE_FORMAT = "as608-ef01-single-capture-opaque"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "private-data" / "fingerprint-probes"


def receive_probe(port, deadline):
    fields = wait_marker(port, "FPPROBE ", deadline, lambda text: print(text, flush=True)).split()
    if len(fields) != 7 or fields[1] != "1":
        raise ValueError("Invalid probe header/version")
    source = dict(zip(("capacity", "security_level", "packet_bytes", "system_id"), map(int, fields[2:6])))
    source["device_address"] = fields[6]
    validate_parameters({**source, "slot_id": 0})
    data = bytearray()
    while True:
        line = read_line(port, deadline)
        if line.startswith("FPDATA "):
            encoded = line[7:]
            if not HEX_LINE.fullmatch(encoded) or len(encoded) % 2:
                raise ValueError("Malformed probe hex")
            data.extend(bytes.fromhex(encoded))
            if len(data) > MAX_BYTES:
                raise ValueError("Probe exceeds 2048-byte transfer limit")
        elif line.startswith("FPEND "):
            fields = line.split()
            if (len(fields) != 3 or not data or int(fields[1]) != len(data)
                    or not re.fullmatch(r"[0-9A-Fa-f]{8}", fields[2])
                    or int(fields[2], 16) != zlib.crc32(data)):
                raise ValueError("Probe byte count/CRC mismatch")
            return bytes(data), source
        else:
            raise ValueError("Unexpected line in probe transfer")


def probe_record(data, source, scanner_id, group):
    return {"schema_version": 1, "kind": "single_capture_probe", "probe_id": str(uuid.uuid4()),
        "probe_format": PROBE_FORMAT, "scanner_id": canonical_uuid(scanner_id),
        "compatibility_group": label(group), "received_at": datetime.now(timezone.utc).isoformat(),
        "byte_length": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "probe_base64": base64.b64encode(data).decode("ascii"), "source": source}


def validate_probe(record):
    if not isinstance(record, dict) or not isinstance(record.get("source"), dict):
        raise ValueError("Probe record and source must be objects")
    for field in ("probe_id", "scanner_id"):
        if not isinstance(record.get(field), str):
            raise ValueError("Probe and scanner UUIDs must be strings")
    if (type(record.get("schema_version")) is not int or record["schema_version"] != 1
            or record.get("kind") != "single_capture_probe" or record.get("probe_format") != PROBE_FORMAT):
        raise ValueError("Not a supported single-capture probe; enrollment backups are different")
    canonical_uuid(record["probe_id"])
    canonical_uuid(record["scanner_id"])
    label(record["compatibility_group"])
    validate_parameters({**record["source"], "slot_id": 0})
    data = base64.b64decode(record["probe_base64"], validate=True)
    if (type(record["byte_length"]) is not int or not 1 <= len(data) <= MAX_BYTES
            or len(data) != record["byte_length"] or hashlib.sha256(data).hexdigest() != record["sha256"]):
        raise ValueError("Probe size/hash mismatch")
    return data


def compare_probe(port, data, source, slot, deadline, method="search"):
    if type(slot) is not int or not 0 <= slot <= 65534 or not 1 <= len(data) <= MAX_BYTES:
        raise ValueError("Invalid slot or probe size")
    if method not in ("search", "direct"):
        raise ValueError("Unknown comparison method")
    command = "k" if method == "direct" else "j"
    ready_marker = "FPPROBEDIRECTREADY " if method == "direct" else "FPPROBEREADY "
    result_marker = "FPPROBEDIRECTRESULT " if method == "direct" else "FPPROBERESULT "
    port.write(f"{command} {slot} {len(data)} {zlib.crc32(data):08X}\n".encode("ascii"))
    ready = wait_marker(port, ready_marker, deadline).split()
    if (len(ready) != 6 or int(ready[1]) != slot or int(ready[2]) != len(data)
            or int(ready[3]) != source["security_level"] or int(ready[4]) != source["system_id"]
            or ready[5] != source["device_address"]):
        raise ValueError("Comparison target/settings differ from captured probe; no bytes sent")
    for offset in range(0, len(data), 32):
        port.write((data[offset:offset+32].hex()+"\n").encode("ascii"))
        port.flush()
        time.sleep(0.02)
    result = wait_marker(port, result_marker, deadline).split()
    if (len(result) != 4 or int(result[1]) != slot or result[2] not in ("MATCH", "NO_MATCH")
            or not result[3].isdigit() or not 0 <= int(result[3]) <= 65535
            or (result[2] == "NO_MATCH" and int(result[3]) != 0)):
        raise ValueError("Invalid comparison result")
    return {"reference_slot": slot, "result": result[2], "raw_score": int(result[3]) if result[2] == "MATCH" else None, "method": method}


def read_probe(path):
    if path.stat().st_size > 16384:
        raise ValueError("Probe file exceeds 16 KiB")
    record = json.loads(path.read_text(encoding="utf-8"))
    return record, validate_probe(record)


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental replacement of earlier captures/results.
    with path.open("x", encoding="utf-8") as stream:
        write_json(stream, value)
    if json.loads(path.read_text(encoding="utf-8")) != value:
        raise ValueError("Saved file verification failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--port", required=True)
    capture.add_argument("--scanner-id", type=canonical_uuid, required=True)
    capture.add_argument("--compatibility-group", type=label, default="as608-unit-1")
    capture.add_argument("--out", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--port", required=True)
    compare.add_argument("--probe", type=Path, required=True)
    compare.add_argument("--slot", type=int, required=True)
    compare.add_argument("--method", choices=["search", "direct"], default="direct")
    compare.add_argument("--scanner-id", type=canonical_uuid, required=True)
    compare.add_argument("--compatibility-group", type=label, default="as608-unit-1")
    compare.add_argument("--out", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = args.out or DEFAULT_ROOT / (f"{args.command}-{stamp}-{uuid.uuid4().hex[:8]}.json")
    if output.exists():
        parser.error("Choose a new output filename")
    try:
        if args.command == "capture":
            print("Lift your finger first; present it once when prompted. This does not enroll or match.", flush=True)
            with connect(args.port) as port:
                port.write(b"q\n")
                data, source = receive_probe(port, time.monotonic()+150)
            record = probe_record(data, source, args.scanner_id, args.compatibility_group)
            validate_probe(record)
            save_new(output, record)
            print(f"Saved verified probe: {output} ({len(data)} bytes). Gallery unchanged.")
        else:
            record, data = read_probe(args.probe)
            if record["scanner_id"] != args.scanner_id or record["compatibility_group"] != args.compatibility_group:
                raise ValueError("Use the same commissioned scanner and compatibility group for this first experiment")
            print("Keep all fingers OFF the scanner. Comparing saved bytes only; no enrollment or fresh capture.", flush=True)
            with connect(args.port) as port:
                result = compare_probe(port, data, record["source"], args.slot, time.monotonic()+45, method=args.method)
            report = {"schema_version": 1, "probe_id": record["probe_id"], "probe_sha256": record["sha256"],
                "scanner_id": args.scanner_id, "compatibility_group": args.compatibility_group,
                "compared_at": datetime.now(timezone.utc).isoformat(), **result}
            save_new(output, report)
            print(f"{result['result']} against slot {args.slot}; raw score={result['raw_score']} (not a percentage).")
            print(f"Result saved: {output}")
    except (OSError, ValueError, KeyError, TypeError, TimeoutError) as exc:
        parser.exit(1, f"Experiment stopped: {exc}\n")


if __name__ == "__main__":
    main()
