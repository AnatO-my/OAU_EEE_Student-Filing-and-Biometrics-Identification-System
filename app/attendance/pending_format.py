"""Bounded v1 USB capture interchange. Digests detect damage, not device identity."""
import base64
import binascii
from dataclasses import dataclass, field
import hashlib
import json
import re
import uuid


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LINE_BYTES = 4096
MAX_EVENTS = 512
MAX_PROBE_BYTES = 2048
PROBE_FORMAT = "as608-ef01-single-capture-opaque"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


# Keep parser failures safe to return without exposing submitted evidence.
class BatchFormatError(ValueError):
    """Messages must never include submitted fields or biometric payloads."""


# Hold one validated capture while hiding biometric bytes from repr output.
@dataclass(frozen=True)
class Capture:
    event_id: uuid.UUID
    boot_id: uuid.UUID
    uptime_ms: int
    probe: bytes = field(repr=False)


# Return parsed batch metadata, ordered captures, and the exact-file digest.
@dataclass(frozen=True)
class CaptureFile:
    metadata: dict
    interrupted_write_pending: bool
    events: tuple[Capture, ...]
    file_sha256: str


# Read a request body incrementally so oversized uploads stop at the fixed cap.
def read_batch_stream(stream):
    """Read at most the file limit plus one byte, without multipart buffering."""
    if stream is None:
        raise BatchFormatError("Capture batch is empty.")
    data = bytearray()
    while len(data) <= MAX_FILE_BYTES:
        chunk = stream.read(min(65536, MAX_FILE_BYTES + 1 - len(data)))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
    raise BatchFormatError("Capture batch exceeds the 2 MiB limit.")


# Enforce an exact key set so unsupported fields cannot smuggle identities.
def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise BatchFormatError("Capture batch has missing or unsupported fields.")


# Accept only nonzero UUIDs in their canonical lowercase textual form.
def _uuid(value):
    if not isinstance(value, str):
        raise BatchFormatError("Capture identifiers must be nonzero canonical UUIDs.")
    parsed = uuid.UUID(value)
    if not parsed.int or str(parsed) != value:
        raise BatchFormatError("Capture identifiers must be nonzero canonical UUIDs.")
    return parsed


# Reject booleans as well as integers outside the field's allowed range.
def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise BatchFormatError("Capture batch contains an invalid integer.")


# JSON object parsing uses this hook to reject ambiguous duplicate keys.
def _unique_fields(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise BatchFormatError("Capture batch contains a duplicate JSON field.")
        value[key] = item
    return value


# Do not let Python's permissive JSON parser accept NaN or infinity.
def _reject_constant(_value):
    raise BatchFormatError("Non-finite JSON numbers are unsupported.")


# Validate bounded JSONL input, per-event ordering, and the body digest.
def _parse(data):
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_FILE_BYTES or not data.endswith(b"\n"):
        raise BatchFormatError("Capture batch is incomplete or exceeds the 2 MiB limit.")
    # Bound splitting too, so many tiny lines cannot create millions of objects.
    parts = data.split(b"\n", MAX_EVENTS + 2)
    if parts[-1] != b"":
        raise BatchFormatError("Capture batch exceeds the record limit.")
    lines = parts[:-1]
    if not 2 <= len(lines) <= MAX_EVENTS + 2 or any(len(line) > MAX_LINE_BYTES for line in lines):
        raise BatchFormatError("Capture batch exceeds the record or line limit.")
    values = [json.loads(line.decode("utf-8"), object_pairs_hook=_unique_fields,
                         parse_constant=_reject_constant) for line in lines]
    header, trailer = values[0], values[-1]
    _fields(header, "kind schema_version device_uuid batch_uuid class_session_uuid scanner_uuid "
                    "compatibility_group probe_format source clock interrupted_write_pending")
    if header["kind"] != "capture_batch" or type(header["schema_version"]) is not int or header["schema_version"] != 1 or header["probe_format"] != PROBE_FORMAT:
        raise BatchFormatError("Unsupported capture batch format or version.")
    for key in ("device_uuid", "batch_uuid", "class_session_uuid", "scanner_uuid"):
        _uuid(header[key])
    group = header["compatibility_group"]
    if not isinstance(group, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,79}", group):
        raise BatchFormatError("Invalid scanner compatibility label.")
    source = header["source"]
    _fields(source, "capacity security_level packet_bytes system_id device_address")
    for name, minimum in (("capacity", 1), ("security_level", 0), ("system_id", 0)):
        _integer(source[name], minimum, 65535)
    if type(source["packet_bytes"]) is not int or source["packet_bytes"] not in (32, 64, 128, 256):
        raise BatchFormatError("Invalid scanner packet size.")
    if not isinstance(source["device_address"], str) or not re.fullmatch(r"[0-9A-F]{8}", source["device_address"]):
        raise BatchFormatError("Invalid scanner address.")
    clock = header["clock"]
    _fields(clock, "basis wall_clock_verified timezone")
    if clock["basis"] != "boot_elapsed" or clock["wall_clock_verified"] is not False or clock["timezone"] is not None:
        raise BatchFormatError("Only unverified boot-elapsed capture time is supported.")
    if type(header["interrupted_write_pending"]) is not bool:
        raise BatchFormatError("Invalid interrupted-write state.")
    events, seen, last_uptime = [], set(), {}
    for value in values[1:-1]:
        _fields(value, "kind event_uuid boot_uuid uptime_ms captured_at probe_base64")
        if value["kind"] != "capture" or value["captured_at"] is not None:
            raise BatchFormatError("Only unidentified captures without wall-clock time are supported.")
        event_id, boot_id = _uuid(value["event_uuid"]), _uuid(value["boot_uuid"])
        uptime = value["uptime_ms"]
        _integer(uptime, 0, 2**64 - 1)
        if event_id in seen or uptime < last_uptime.get(boot_id, -1):
            raise BatchFormatError("Duplicate event UUID or elapsed time moving backwards.")
        seen.add(event_id)
        last_uptime[boot_id] = uptime
        encoded = value["probe_base64"]
        if not isinstance(encoded, str) or not 1 <= len(encoded) <= 4 * ((MAX_PROBE_BYTES + 2) // 3):
            raise BatchFormatError("Invalid or oversized capture probe.")
        probe = base64.b64decode(encoded, validate=True)
        if not 1 <= len(probe) <= MAX_PROBE_BYTES or base64.b64encode(probe).decode("ascii") != encoded:
            raise BatchFormatError("Invalid or noncanonical capture probe encoding.")
        events.append(Capture(event_id, boot_id, uptime, probe))
    _fields(trailer, "kind record_count sha256")
    body = b"\n".join(lines[:-1]) + b"\n"
    if (trailer["kind"] != "end" or type(trailer["record_count"]) is not int
            or trailer["record_count"] != len(events) or not isinstance(trailer["sha256"], str)
            or not SHA256_PATTERN.fullmatch(trailer["sha256"])
            or trailer["sha256"] != hashlib.sha256(body).hexdigest()):
        raise BatchFormatError("Capture batch digest or record count does not match.")
    interrupted = header.pop("interrupted_write_pending")
    return CaptureFile(header, interrupted, tuple(events), hashlib.sha256(data).hexdigest())


# Normalize malformed-input exceptions without forwarding private payload data.
def parse_capture_file(data):
    try:
        return _parse(data)
    except BatchFormatError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, binascii.Error):
        # JSON/Base64 exception messages can contain private input. Never forward them.
        raise BatchFormatError("Malformed capture batch; no data was accepted.") from None
