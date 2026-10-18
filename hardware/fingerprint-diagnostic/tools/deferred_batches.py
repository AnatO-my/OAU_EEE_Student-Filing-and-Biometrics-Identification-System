"""Download pending AS608 capture batches over USB serial; no attendance/database writes."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time
import uuid
import zlib

from portable_template import (connect, read_line, canonical_uuid, label,
                               validate_parameters, HEX_LINE)
from probe_experiment import PROBE_FORMAT, DEFAULT_ROOT

HEADER_BYTES = 164
EVENT_FIXED_BYTES = 50
MAX_PROBE_BYTES = 2048
MAX_EVENTS = 512
MAX_FILE_BYTES = 2 * 1024 * 1024


def status_line(port, deadline):
    """Allow bounded SDK diagnostics before a receipt, never inside data blocks."""
    buffered = bytearray()
    while time.monotonic() < deadline:
        raw = port.readline(4096 - len(buffered))
        if not raw:
            continue
        buffered.extend(raw)
        if len(buffered) >= 4096:
            raise ValueError('Oversized device status line')
        if buffered.endswith(b'\n'):
            line = buffered.decode('ascii', errors='replace').strip()
            if line.startswith('FP') and len(line) >= 256:
                raise ValueError('Oversized protocol status')
            return line
    raise TimeoutError('Device status receipt timed out')


def wait(port, marker, deadline):
    for _ in range(200):
        line = status_line(port, deadline)
        if line.startswith(('FPBERROR ', 'FPERROR')):
            # Avoid echoing arbitrary device text into logs with private data.
            raise ValueError('Device stopped the batch operation; inspect its local status')
        if line.startswith(marker):
            return line
    raise ValueError('Too many unexpected device lines')


def checked_uuid(raw):
    return canonical_uuid(str(uuid.UUID(bytes=raw)))


def check_seal(raw, magic):
    if len(raw) < 8 or raw[:4] != magic or struct.unpack('>I', raw[-4:])[0] != zlib.crc32(raw[:-4]):
        raise ValueError('Damaged stored block')


def decode_header(raw):
    if len(raw) != HEADER_BYTES:
        raise ValueError('Invalid header size')
    check_seal(raw, b'FPB1')
    group_bytes = raw[68:148]
    text, separator, padding = group_bytes.partition(b'\0')
    if not separator or any(padding):
        raise ValueError('Invalid compatibility-group padding')
    group = label(text.decode('ascii'))
    capacity, security, packet, system, address = struct.unpack('>HHHHI', raw[148:160])
    source = dict(capacity=capacity, security_level=security, packet_bytes=packet,
                  system_id=system, device_address=f'{address:08X}')
    validate_parameters({**source, 'slot_id': 0})
    return dict(kind='capture_batch', schema_version=1,
                device_uuid=checked_uuid(raw[4:20]), batch_uuid=checked_uuid(raw[20:36]),
                class_session_uuid=checked_uuid(raw[36:52]), scanner_uuid=checked_uuid(raw[52:68]),
                compatibility_group=group, probe_format=PROBE_FORMAT, source=source,
                clock=dict(basis='boot_elapsed', wall_clock_verified=False, timezone=None))


def decode_event(raw):
    if not EVENT_FIXED_BYTES + 1 <= len(raw) <= EVENT_FIXED_BYTES + MAX_PROBE_BYTES:
        raise ValueError('Invalid event size')
    check_seal(raw, b'FPE1')
    uptime, length = struct.unpack('>QH', raw[36:46])
    if length != len(raw) - EVENT_FIXED_BYTES:
        raise ValueError('Probe length disagrees with stored event')
    return dict(kind='capture', event_uuid=checked_uuid(raw[4:20]),
                boot_uuid=checked_uuid(raw[20:36]), uptime_ms=uptime, captured_at=None,
                probe_base64=base64.b64encode(raw[46:-4]).decode('ascii'))


def receive_block(port, kind, deadline):
    fields = read_line(port, deadline).split()
    if len(fields) != 4 or fields[:2] != ['FPBLOCK', kind] or not fields[2].isdigit() or not re.fullmatch(r'[0-9A-Fa-f]{8}', fields[3]):
        raise ValueError('Invalid block header')
    length, checksum = int(fields[2]), int(fields[3], 16)
    if (kind == 'header' and length != HEADER_BYTES) or (kind == 'event' and not EVENT_FIXED_BYTES < length <= EVENT_FIXED_BYTES + MAX_PROBE_BYTES):
        raise ValueError('Oversized/invalid block')
    data = bytearray()
    while len(data) < length:
        line = read_line(port, deadline)
        if not line.startswith('FPDATA ') or not HEX_LINE.fullmatch(line[7:]) or len(line[7:]) % 2:
            raise ValueError('Invalid block data')
        data.extend(bytes.fromhex(line[7:]))
        if len(data) > length:
            raise ValueError('Block exceeds declared size')
    end = read_line(port, deadline).split()
    if end != ['FPEND', str(length), f'{checksum:08X}'] or zlib.crc32(data) != checksum:
        raise ValueError('Block checksum/receipt mismatch')
    return bytes(data)


def json_line(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def receive_batch(port, requested_batch, deadline):
    fields = wait(port, 'FPBATCH ', deadline).split()
    if len(fields) != 4 or fields[1] != '1' or not fields[2].isdigit() or fields[3] not in ('0', '1'):
        raise ValueError('Invalid batch preamble')
    count = int(fields[2])
    if count > MAX_EVENTS:
        raise ValueError('Batch count exceeds limit')
    wire_hash = hashlib.sha256()
    raw = receive_block(port, 'header', deadline)
    wire_hash.update(raw)
    header = decode_header(raw)
    if header['batch_uuid'] != canonical_uuid(requested_batch):
        raise ValueError('Downloaded wrong batch')
    header['interrupted_write_pending'] = fields[3] == '1'
    records, seen = [], set()
    last_uptime = {}
    for _ in range(count):
        raw = receive_block(port, 'event', deadline)
        wire_hash.update(raw)
        event = decode_event(raw)
        if event['event_uuid'] in seen:
            raise ValueError('Duplicate event UUID inside batch')
        previous = last_uptime.get(event['boot_uuid'], -1)
        if event['uptime_ms'] < previous:
            raise ValueError('Capture times move backwards within a boot')
        last_uptime[event['boot_uuid']] = event['uptime_ms']
        seen.add(event['event_uuid'])
        records.append(event)
    end = read_line(port, deadline).split()
    if end != ['FPBATCHEND', str(count), wire_hash.hexdigest()]:
        raise ValueError('Incomplete batch or stream digest mismatch')
    body = b''.join(json_line(record) for record in [header, *records])
    trailer = dict(kind='end', record_count=count, sha256=hashlib.sha256(body).hexdigest())
    return body + json_line(trailer)


def validate_file(data):
    """Validate the downloaded JSONL before any later backend/matcher use."""
    if len(data) > MAX_FILE_BYTES or not data.endswith(b'\n'):
        raise ValueError('Incomplete/oversized batch file')
    lines = data.splitlines(keepends=True)
    if not 2 <= len(lines) <= MAX_EVENTS + 2:
        raise ValueError('Invalid batch record count')
    values = [json.loads(line, object_pairs_hook=unique_fields) for line in lines]
    header, trailer = values[0], values[-1]
    if not isinstance(header, dict) or not isinstance(trailer, dict):
        raise ValueError('Header and trailer must be objects')
    if header.get('kind') != 'capture_batch' or type(header.get('schema_version')) is not int or header['schema_version'] != 1 or header.get('probe_format') != PROBE_FORMAT:
        raise ValueError('Unsupported capture batch format')
    for key in ('batch_uuid', 'device_uuid', 'class_session_uuid', 'scanner_uuid'):
        canonical_uuid(header[key])
    label(header['compatibility_group'])
    if type(header['interrupted_write_pending']) is not bool or header['clock'] != dict(basis='boot_elapsed', wall_clock_verified=False, timezone=None):
        raise ValueError('Unsupported clock/recovery state')
    validate_parameters({**header['source'], 'slot_id': 0})
    seen, last_uptime = set(), {}
    for record in values[1:-1]:
        if not isinstance(record, dict) or record.get('kind') != 'capture' or record.get('captured_at') is not None:
            raise ValueError('Unsupported capture record')
        event = canonical_uuid(record['event_uuid'])
        boot = canonical_uuid(record['boot_uuid'])
        uptime = record['uptime_ms']
        if event in seen or type(uptime) is not int or not 0 <= uptime <= 2**64-1 or uptime < last_uptime.get(boot, -1):
            raise ValueError('Duplicate event or invalid elapsed time')
        seen.add(event); last_uptime[boot] = uptime
        encoded = record['probe_base64']
        if not isinstance(encoded, str) or len(encoded) > 4*((MAX_PROBE_BYTES+2)//3):
            raise ValueError('Oversized probe')
        if not 1 <= len(base64.b64decode(encoded, validate=True)) <= MAX_PROBE_BYTES:
            raise ValueError('Invalid probe')
    if trailer.get('kind') != 'end' or type(trailer.get('record_count')) is not int or trailer['record_count'] != len(seen) or trailer.get('sha256') != hashlib.sha256(b''.join(lines[:-1])).hexdigest():
        raise ValueError('Batch digest/count mismatch')
    return header, len(seen)


def save_download(path, data):
    validate_file(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    with temporary.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    saved = temporary.read_bytes()
    if saved != data:
        raise ValueError('Local file readback mismatch; partial retained')
    validate_file(saved)
    # Hard-link creation refuses an existing target, unlike replace/rename.
    os.link(temporary, path)
    temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('initialize-empty', 'begin', 'arm', 'stop', 'list', 'download'):
        command = sub.add_parser(name)
        command.add_argument('--port', required=True)
        if name in ('begin', 'arm', 'download'):
            command.add_argument('--batch', type=canonical_uuid, required=True)
        if name == 'begin':
            command.add_argument('--class-session', type=canonical_uuid, required=True)
            command.add_argument('--scanner-id', type=canonical_uuid, required=True)
            command.add_argument('--compatibility-group', type=label, default='as608-unit-1')
        if name == 'download':
            command.add_argument('--out', type=Path)
        if name == 'arm':
            command.add_argument('--watch', action='store_true', help='Show save/retry feedback until Ctrl+C, then stop capture')
    check = sub.add_parser('validate')
    check.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            if args.file.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('File exceeds size limit')
            header, count = validate_file(args.file.read_bytes())
            print(f'Valid pending batch: {count} captures. Identities and wall-clock times require reconciliation.')
            return
        if args.command == 'begin' and len(args.compatibility_group) > 79:
            raise ValueError('Device compatibility group is limited to 79 characters')
        output = None
        if args.command == 'download':
            output = args.out or DEFAULT_ROOT / 'batches' / f'{args.batch}-{uuid.uuid4().hex[:8]}.jsonl'
            if output.exists():
                raise ValueError('Choose a new output file')
        with connect(args.port) as port:
            deadline = time.monotonic() + 300
            if args.command == 'initialize-empty':
                port.write(b'z initialize EMPTY\n')
                wait(port, 'FPBINITIALIZED ', deadline)
                print('Previously erased filesystem partition initialized. Existing data would block this operation.')
            elif args.command == 'download':
                port.write(f'z export {args.batch}\n'.encode('ascii'))
                data = receive_batch(port, args.batch, deadline)
                save_download(output, data)
                header, count = validate_file(data)
                print(f'Saved {count} pending captures: {output}. Device files retained.')
                if header['interrupted_write_pending']:
                    print('An interrupted device write remains; preserve device files for recovery.')
            elif args.command == 'begin':
                port.write(f'z begin {args.batch} {args.class_session} {args.scanner_id} {args.compatibility_group}\n'.encode('ascii'))
                fields = wait(port, 'FPBCREATED ', deadline).split()
                if len(fields) != 3 or fields[1] != args.batch:
                    raise ValueError('Unexpected creation receipt')
                canonical_uuid(fields[2])
                print('Batch created. Arm it explicitly to start offline capture.')
            elif args.command == 'arm':
                port.write(f'z arm {args.batch}\n'.encode('ascii'))
                fields = wait(port, 'FPBARMED ', deadline).split()
                if len(fields) < 3 or fields[1] != args.batch or not fields[2].isdigit() or int(fields[2]) >= MAX_EVENTS:
                    raise ValueError('Unexpected arm receipt')
                print('Armed. Lift then scan each finger once; lift between attempts. Keep USB power connected.')
                if args.watch:
                    try:
                        while True:
                            try:
                                line = status_line(port, time.monotonic() + 60)
                            except TimeoutError:
                                continue
                            if line.startswith('FPBSAVED '):
                                print('Capture saved; pending identity match. Lift finger.', flush=True)
                            elif line.startswith('FPBRETRY '):
                                print('Capture rejected; lift and retry.', flush=True)
                            elif line.startswith('FPBERROR '):
                                raise ValueError('Device stopped capture; preserve its files and inspect storage/scanner status')
                    except KeyboardInterrupt:
                        pass
                    finally:
                        port.write(b'z stop\n'); wait(port, 'FPBSTOPPED', time.monotonic() + 10)
                        print('Capture stopped. Saved files retained.')
            elif args.command == 'stop':
                port.write(b'z stop\n'); wait(port, 'FPBSTOPPED', deadline)
                print('Capture stopped. Saved files retained.')
            else:
                port.write(b'z list\n')
                if wait(port, 'FPBLISTBEGIN ', deadline) != 'FPBLISTBEGIN 1':
                    raise ValueError('Unsupported listing protocol')
                for _ in range(1024):
                    line = read_line(port, deadline)
                    if line == 'FPBLISTEND':
                        break
                    fields = line.split()
                    if len(fields) == 2 and fields[0] == 'FPBDAMAGED':
                        print(f'{canonical_uuid(fields[1])}: damaged; retained for recovery')
                    elif len(fields) == 4 and fields[0] == 'FPBLIST' and fields[2].isdigit() and fields[3] in ('0', '1'):
                        print(f'{canonical_uuid(fields[1])}: {int(fields[2])} captures; interrupted write={fields[3]}')
                    else:
                        raise ValueError('Invalid batch listing')
                else:
                    raise ValueError('Batch listing exceeds limit')
    except (OSError, ValueError, KeyError, TypeError, TimeoutError) as exc:
        parser.exit(1, f'Batch operation stopped: {exc}\n')


if __name__ == '__main__':
    main()
