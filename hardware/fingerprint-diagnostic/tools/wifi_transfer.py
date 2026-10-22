"""Opt-in TLS delivery of ESP32 exports to a laptop; no website/database writes."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import getpass
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import time
import uuid

import deferred_batches as batches
from portable_template import (FingerprintTemplateRecord, canonical_uuid, connect,
                               label, read_line, validate_parameters)

PRIVATE_ROOT = Path(__file__).resolve().parents[3] / 'private-data'
MAX_CSV_BYTES = 256 * 1024
MAX_TEMPLATE_WIRE_BYTES = 18 + 2048
MAX_CONFIG_BYTES = 4096
MAX_CONFIG_JSON = 65536
MIN_TLS_TIME = 1704067200
MAX_TLS_TIME = 2145916799
CSV_HEADER = b'event_uuid,device_uuid,local_datetime,slot,template_sha256,raw_score\n'
HEX256 = re.compile(r'[0-9a-f]{64}\Z')
SLOT = re.compile(r'(?:0|[1-9][0-9]{0,4})\Z')
HOST = re.compile(r'[A-Za-z0-9.-]{1,253}\Z')


class TransferCancelled(Exception):
    pass


def exact_uuid(value):
    if not isinstance(value, str) or canonical_uuid(value) != value:
        raise ValueError('Expected a canonical nonzero UUID')
    return value


def host_name(value):
    if not isinstance(value, str) or not HOST.fullmatch(value) or value.startswith(('.', '-')) or value.endswith(('.', '-')):
        raise ValueError('Use an IPv4 address or DNS hostname')
    if any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-') for part in value.split('.')):
        raise ValueError('Invalid receiver hostname')
    if re.fullmatch(r'[0-9.]+', value):
        ipaddress.IPv4Address(value)
    return value


def printable(value, minimum, maximum):
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and all(32 <= ord(char) <= 126 for char in value))


def private_json(path):
    if path.stat().st_size > MAX_CONFIG_JSON:
        raise ValueError('Private configuration is too large')
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=batches.unique_fields)
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported private configuration')
    return value


def validate_device_config(value):
    expected = {'schema_version', 'device_uuid', 'ssid', 'password', 'host', 'port',
                'token', 'certificate_sha256', 'ca_pem'}
    if set(value) != expected or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Invalid device configuration fields')
    exact_uuid(value['device_uuid'])
    if not printable(value['ssid'], 1, 32) or not printable(value['password'], 8, 63):
        raise ValueError('SSID/password must fit the supported WPA network limits')
    host_name(value['host'])
    if type(value['port']) is not int or not 1 <= value['port'] <= 65535:
        raise ValueError('Invalid receiver port')
    if any(not isinstance(value[key], str) or not HEX256.fullmatch(value[key]) for key in ('token', 'certificate_sha256')):
        raise ValueError('Invalid device credential or certificate pin')
    ca = value['ca_pem']
    if not isinstance(ca, str) or not ca.startswith('-----BEGIN CERTIFICATE-----\n') or not ca.endswith('-----END CERTIFICATE-----\n'):
        raise ValueError('Invalid receiver certificate')
    try:
        ca_bytes = ca.encode('ascii')
        der = ssl.PEM_cert_to_DER_cert(ca)
    except (UnicodeError, ValueError) as exc:
        raise ValueError('Invalid receiver certificate encoding') from exc
    if len(ca_bytes) > 3000 or b'\0' in ca_bytes or hashlib.sha256(der).hexdigest() != value['certificate_sha256']:
        raise ValueError('Receiver certificate/pin mismatch')
    payload = (b'FPW1' + struct.pack('>H', value['port'])
               + b''.join(value[key].encode('ascii') + b'\0' for key in
                          ('ssid', 'password', 'host', 'token', 'certificate_sha256', 'ca_pem')))
    if len(payload) > MAX_CONFIG_BYTES:
        raise ValueError('Device configuration exceeds firmware limit')
    return payload


def validate_receiver_config(value, base):
    expected = {'schema_version', 'host', 'port', 'certificate', 'private_key', 'output_dir', 'devices'}
    if set(value) != expected or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Invalid receiver configuration fields')
    host_name(value['host'])
    if type(value['port']) is not int or not 1 <= value['port'] <= 65535:
        raise ValueError('Invalid receiver port')
    if not isinstance(value['devices'], list) or not 1 <= len(value['devices']) <= 32:
        raise ValueError('Receiver requires an explicit device allowlist')
    seen, credentials = set(), set()
    for device in value['devices']:
        if not isinstance(device, dict) or set(device) != {'device_uuid', 'token', 'scanner_id', 'gallery_id', 'compatibility_group'}:
            raise ValueError('Invalid commissioned device entry')
        for key in ('device_uuid', 'scanner_id', 'gallery_id'):
            exact_uuid(device[key])
        if not isinstance(device['token'], str) or not HEX256.fullmatch(device['token']):
            raise ValueError('Invalid commissioned device credential')
        label(device['compatibility_group'])
        if len(device['compatibility_group']) > 79 or device['device_uuid'] in seen or device['token'] in credentials:
            raise ValueError('Duplicate device/credential or oversized compatibility label')
        seen.add(device['device_uuid']); credentials.add(device['token'])
    result = dict(value)
    for key in ('certificate', 'private_key', 'output_dir'):
        if not isinstance(value[key], str) or not value[key]:
            raise ValueError('Invalid receiver file location')
        result[key] = (base / value[key]).resolve()
    return result


def validate_csv(data, expected_device=None):
    if expected_device is not None:
        exact_uuid(expected_device)
    if not isinstance(data, bytes) or len(data) > MAX_CSV_BYTES or not data.startswith(CSV_HEADER) or not data.endswith(b'\n'):
        raise ValueError('Invalid or incomplete check-in CSV')
    rows = data[len(CSV_HEADER):].splitlines(keepends=True)
    seen, origin = set(), None
    for raw in rows:
        if len(raw) >= 192 or not raw.endswith(b'\n') or b'\r' in raw:
            raise ValueError('Invalid check-in row length/terminator')
        try:
            fields = raw[:-1].decode('ascii').split(',')
        except UnicodeError as exc:
            raise ValueError('Invalid check-in row encoding') from exc
        if len(fields) != 6:
            raise ValueError('Invalid check-in column count')
        event, device, timestamp, slot, digest, score = fields
        exact_uuid(event); exact_uuid(device)
        if event in seen or (expected_device is not None and device != expected_device) or (origin is not None and device != origin):
            raise ValueError('Duplicate check-in event or wrong device')
        origin = device
        if not re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}', timestamp):
            raise ValueError('Invalid check-in date')
        datetime.fromisoformat(timestamp)
        if any(not SLOT.fullmatch(number) or int(number) > 65535 for number in (slot, score)) or not HEX256.fullmatch(digest):
            raise ValueError('Invalid check-in slot, score or template digest')
        seen.add(event)
    return len(rows)


def decode_template(data, identifier):
    if not SLOT.fullmatch(identifier) or int(identifier) > 65534:
        raise ValueError('Invalid template slot')
    if not 19 <= len(data) <= MAX_TEMPLATE_WIRE_BYTES or data[:4] != b'FPT1':
        raise ValueError('Invalid template envelope')
    slot, capacity, security, packet, system, address = struct.unpack('>HHHHHI', data[4:18])
    parameters = dict(slot_id=slot, capacity=capacity, security_level=security,
                      packet_bytes=packet, system_id=system, device_address=f'{address:08X}')
    validate_parameters(parameters)
    if slot != int(identifier):
        raise ValueError('Template slot disagrees with request')
    return data[18:], parameters


def receive_file(stream, kind, deadline):
    fields = read_line(stream, deadline).split()
    if (len(fields) != 5 or fields[:3] != ['FPFILE', '1', kind]
            or not fields[3].isdigit() or not HEX256.fullmatch(fields[4])):
        raise ValueError('Invalid file preamble')
    length, digest = int(fields[3]), fields[4]
    limit = MAX_CSV_BYTES if kind == 'csv' else MAX_TEMPLATE_WIRE_BYTES
    if not 1 <= length <= limit:
        raise ValueError('File exceeds transport limit')
    data = bytearray()
    while len(data) < length:
        line = read_line(stream, deadline)
        if not line.startswith('FPDATA ') or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}){1,32}', line[7:]):
            raise ValueError('Invalid file data frame')
        data.extend(bytes.fromhex(line[7:]))
        if len(data) > length:
            raise ValueError('File exceeds declared length')
    if read_line(stream, deadline).split() != ['FPFILEEND', str(length), digest] or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Incomplete file or digest mismatch')
    return bytes(data), digest


def batch_wire_digest(data):
    values = [json.loads(line) for line in data.splitlines()]
    header = values[0]
    source = header['source']
    raw = (b'FPB1' + b''.join(uuid.UUID(header[key]).bytes for key in
                             ('device_uuid', 'batch_uuid', 'class_session_uuid', 'scanner_uuid'))
           + header['compatibility_group'].encode('ascii').ljust(80, b'\0')
           + struct.pack('>HHHHI', source['capacity'], source['security_level'],
                         source['packet_bytes'], source['system_id'], int(source['device_address'], 16)))
    def sealed(block):
        import zlib
        return block + struct.pack('>I', zlib.crc32(block))
    digest = hashlib.sha256(sealed(raw))
    for event in values[1:-1]:
        import base64
        probe = base64.b64decode(event['probe_base64'], validate=True)
        raw = (b'FPE1' + uuid.UUID(event['event_uuid']).bytes + uuid.UUID(event['boot_uuid']).bytes
               + struct.pack('>QH', event['uptime_ms'], len(probe)) + probe)
        digest.update(sealed(raw))
    return digest.hexdigest()


def save_verified(path, data, validator):
    validator(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        saved = path.read_bytes()
        validator(saved)
        if saved != data:
            raise ValueError('Existing content-addressed file disagrees; preserve for review')
        return saved
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    with temporary.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    saved = temporary.read_bytes()
    if saved != data:
        raise ValueError('Local readback failed; partial file retained')
    validator(saved)
    try:
        os.link(temporary, path)
    except FileExistsError:
        existing = path.read_bytes()
        validator(existing)
        if existing != data:
            raise ValueError('Existing file conflicts; complete partial file retained')
    temporary.unlink()
    return saved


@dataclass
class SavedTransfer:
    kind: str
    identifier: str
    path: Path
    wire_sha256: str
    file_sha256: str
    count: int

    def receipt(self):
        return (f'FPWRECEIPT 1 {self.kind} {self.identifier} {self.wire_sha256} '
                f'{self.file_sha256} {self.count}\n').encode('ascii')


def save_template(root, data, identifier, device):
    probe, parameters = decode_template(data, identifier)
    wire_hash = hashlib.sha256(data).hexdigest()
    target = root / 'templates' / device['gallery_id'] / f'slot-{int(identifier):05d}-{wire_hash}.fpt.json'
    def validated(saved):
        if len(saved) > 16384:
            raise ValueError('Oversized saved template')
        value = json.loads(saved, object_pairs_hook=batches.unique_fields)
        record = FingerprintTemplateRecord(**value)
        if (record.validated_bytes() != probe or record.student_id is not None
                or record.compatibility_group != device['compatibility_group']
                or record.source != {**parameters, 'scanner_id': device['scanner_id'],
                                     'gallery_id': device['gallery_id'],
                                     'model_label': 'AS608 (user supplied)', 'firmware_version': None}):
            raise ValueError('Saved template provenance mismatch')
        return record
    if target.exists():
        saved = target.read_bytes()
        validated(saved)
    else:
        template_id = str(uuid.uuid5(uuid.UUID(device['gallery_id']), hashlib.sha256(probe).hexdigest()))
        record = FingerprintTemplateRecord.create(
            probe, student_id=None, finger_label='unknown', scanner_id=device['scanner_id'],
            gallery_id=device['gallery_id'], compatibility_group=device['compatibility_group'],
            parameters=parameters, template_id=template_id)
        saved = (json.dumps(asdict(record), indent=2) + '\n').encode('ascii')
        saved = save_verified(target, saved, validated)
    return target, saved, wire_hash


def handle_transfer(stream, send, config, *, deadline=None):
    deadline = deadline or time.monotonic() + 300
    fields = read_line(stream, deadline).split()
    if len(fields) != 6 or fields[:2] != ['FPWIFI', '1']:
        raise ValueError('Invalid transfer request')
    _, _, token, device_id, kind, identifier = fields
    device = next((item for item in config['devices'] if item['device_uuid'] == device_id), None)
    if device is None or not hmac.compare_digest(token, device['token']):
        raise ValueError('Transfer authentication failed')
    if kind not in ('batch', 'csv', 'template'):
        raise ValueError('Unsupported transfer type')
    if kind == 'batch':
        exact_uuid(identifier)
    elif kind == 'csv' and identifier != 'attendance':
        raise ValueError('Invalid check-in identifier')
    elif kind == 'template' and (not SLOT.fullmatch(identifier) or int(identifier) > 65534):
        raise ValueError('Invalid template identifier')
    send(b'FPWREADY 1\n')
    root = config['output_dir'] / device_id
    if kind == 'batch':
        data = batches.receive_batch(stream, identifier, deadline)
        header, count = batches.validate_file(data)
        if (header['device_uuid'] != device_id or header['scanner_uuid'] != device['scanner_id']
                or header['compatibility_group'] != device['compatibility_group']):
            raise ValueError('Batch commissioning metadata disagrees with configured device')
        # FPBATCHEND hashes the binary blocks; bind the recovery flag in the
        # Wi-Fi receipt as well, without changing the established USB frames.
        wire_hash = hashlib.sha256((batch_wire_digest(data) + ':'
                    + ('1' if header['interrupted_write_pending'] else '0')).encode('ascii')).hexdigest()
        target = root / 'batches' / f'{identifier}-{hashlib.sha256(data).hexdigest()}.jsonl'
        saved = save_verified(target, data, batches.validate_file)
    else:
        data, wire_hash = receive_file(stream, kind, deadline)
        if kind == 'csv':
            # Historical local CSV uses fp-terminal identity; transport/batches
            # use fp-deferred identity. Preserve it without rewriting history.
            count = validate_csv(data)
            target = root / 'checkins' / f'attendance-{wire_hash}.csv'
            saved = save_verified(target, data, validate_csv)
        else:
            target, saved, wire_hash = save_template(root, data, identifier, device)
            count = 1
    result = SavedTransfer(kind, identifier, target, wire_hash, hashlib.sha256(saved).hexdigest(), count)
    send(result.receipt())
    return result


class DeadlineReader:
    def __init__(self, connection, deadline):
        self.connection, self.deadline = connection, deadline
        self.stream = connection.makefile('rb')

    def readline(self, size):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Transfer deadline expired')
        self.connection.settimeout(min(10, remaining))
        value = self.stream.readline(size)
        if not value:
            raise EOFError('Transfer disconnected')
        return value

    def close(self):
        self.stream.close()


def tls_context(config):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config['certificate'], config['private_key'])
    return context


def serve(config, bind, once=False):
    context = tls_context(config)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((bind, config['port'])); listener.listen(4)
        print(f'TLS laptop receiver listening on {bind}:{config["port"]}. No website upload.', flush=True)
        while True:
            connection, _ = listener.accept()
            try:
                connection.settimeout(10)
                with context.wrap_socket(connection, server_side=True) as secure:
                    reader = DeadlineReader(secure, time.monotonic() + 300)
                    try:
                        result = handle_transfer(reader, secure.sendall, config)
                    finally:
                        reader.close()
                print(f'Saved {result.kind}: {result.count} record(s): {result.path}. Device originals retained.', flush=True)
            except (OSError, ValueError, TypeError, KeyError, EOFError):
                connection.close()
                print('Transfer rejected or interrupted. Preserve originals and retry; no success receipt confirmed.', flush=True)
                if once:
                    return 1
            if once:
                return 0


def write_private(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.chmod(path, 0o600)


def initialize(folder, host, port, device_id, scanner_id, gallery_id, group, ssid, password, openssl=None):
    host_name(host)
    for identifier in (device_id, scanner_id, gallery_id):
        exact_uuid(identifier)
    label(group)
    if len(group) > 79 or not printable(ssid, 1, 32) or not printable(password, 8, 63):
        raise ValueError('Invalid commissioning labels or Wi-Fi credentials')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid receiver port')
    executable = openssl or shutil.which('openssl')
    if not executable:
        raise ValueError('OpenSSL is required to create the receiver certificate; use --openssl PATH')
    folder.mkdir(parents=True, exist_ok=False)
    cert, key = folder / 'receiver-cert.pem', folder / 'receiver-key.pem'
    openssl_config = folder / 'openssl.cnf'
    openssl_config.write_text('[req]\ndistinguished_name = request_subject\n[request_subject]\n', encoding='ascii')
    # The pinned ESP32 Mbed TLS 2.28 name verifier only matches dNSName.
    # Also retain a true IP SAN for standards-based Python/OpenSSL IP checks.
    san = f'IP:{host},DNS:{host}' if re.fullmatch(r'[0-9.]+', host) else 'DNS:' + host
    result = subprocess.run([str(executable), 'req', '-x509', '-newkey', 'rsa:2048', '-sha256',
                             '-nodes', '-days', '365', '-config', str(openssl_config), '-subj', '/CN=' + host,
                             '-addext', 'subjectAltName=' + san,
                             '-addext', 'extendedKeyUsage=serverAuth',
                             '-addext', 'basicConstraints=critical,CA:TRUE',
                             '-keyout', str(key), '-out', str(cert)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=60, check=False)
    if result.returncode:
        raise ValueError('Certificate creation failed; inspect OpenSSL installation before retrying into a new folder')
    os.chmod(key, 0o600)
    ca = cert.read_text(encoding='ascii').replace('\r\n', '\n')
    token = secrets.token_hex(32)
    device = dict(schema_version=1, device_uuid=device_id, ssid=ssid, password=password,
                  host=host, port=port, token=token, ca_pem=ca,
                  certificate_sha256=hashlib.sha256(ssl.PEM_cert_to_DER_cert(ca)).hexdigest())
    validate_device_config(device)
    receiver = dict(schema_version=1, host=host, port=port, certificate=cert.name,
                    private_key=key.name, output_dir=str(PRIVATE_ROOT / 'fingerprint-wifi' / 'received'),
                    devices=[dict(device_uuid=device_id, token=token, scanner_id=scanner_id,
                                  gallery_id=gallery_id, compatibility_group=group)])
    validate_receiver_config(receiver, folder)
    write_private(folder / 'device.json', device)
    write_private(folder / 'receiver.json', receiver)
    return folder / 'device.json', folder / 'receiver.json'


def wait_status(port, marker, deadline):
    for _ in range(200):
        line = batches.status_line(port, deadline)
        if line.startswith('FPWCANCELLED'):
            raise TransferCancelled('Device operator cancelled the transfer')
        if line.startswith('FPWERROR'):
            raise ValueError('Device rejected Wi-Fi operation; inspect local status')
        if line.startswith(marker):
            return line
    raise ValueError('Missing Wi-Fi status receipt')


def provision(port, value):
    payload = validate_device_config(value)
    if not MIN_TLS_TIME <= int(time.time()) <= MAX_TLS_TIME:
        raise ValueError('Laptop clock is outside firmware TLS clock range')
    port.write(b'w status\n')
    fields = wait_status(port, 'FPWSTATUS ', time.monotonic() + 15).split()
    if len(fields) < 3 or fields[:2] != ['FPWSTATUS', '1'] or fields[2] != value['device_uuid']:
        raise ValueError('Connected device does not match this private configuration')
    digest = hashlib.sha256(payload).hexdigest()
    port.write(f'w configure {len(payload)} {digest}\n'.encode('ascii'))
    if wait_status(port, 'FPWREADY ', time.monotonic() + 15) != f'FPWREADY {len(payload)}':
        raise ValueError('Unexpected Wi-Fi configuration readiness receipt')
    for offset in range(0, len(payload), 64):
        port.write(payload[offset:offset+64]); port.flush(); time.sleep(0.01)
    receipt = wait_status(port, 'FPWCONFIGURED', time.monotonic() + 20)
    if receipt != 'FPWCONFIGURED':
        raise ValueError('Unexpected Wi-Fi configuration receipt')
    set_clock(port)


def set_clock(port):
    now = int(time.time())
    if not MIN_TLS_TIME <= now <= MAX_TLS_TIME:
        raise ValueError('Laptop clock is outside firmware TLS clock range')
    port.write(f'w clock {now}\n'.encode('ascii'))
    if wait_status(port, 'FPWCLOCK', time.monotonic() + 15) != 'FPWCLOCK':
        raise ValueError('TLS clock setup not confirmed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('init', help='Create new private certificate/config files; prompts for Wi-Fi credentials')
    setup.add_argument('--host', required=True)
    setup.add_argument('--port', type=int, default=9443)
    setup.add_argument('--device', type=exact_uuid, required=True)
    setup.add_argument('--scanner-id', type=exact_uuid, required=True)
    setup.add_argument('--gallery-id', type=exact_uuid, required=True)
    setup.add_argument('--compatibility-group', type=label, default='as608-unit-1')
    setup.add_argument('--out-dir', type=Path)
    setup.add_argument('--openssl')
    configure = commands.add_parser('provision', help='Provision private config and TLS clock over USB')
    configure.add_argument('--port', required=True)
    configure.add_argument('--config', type=Path, required=True)
    receiver = commands.add_parser('receive', help='Receive validated files over TLS; never upload to website')
    receiver.add_argument('--config', type=Path, required=True)
    receiver.add_argument('--bind', default='127.0.0.1', help='Laptop IPv4 address to listen on; default loopback only')
    receiver.add_argument('--once', action='store_true')
    for name in ('status', 'forget', 'clock'):
        sub = commands.add_parser(name)
        sub.add_argument('--port', required=True)
    send = commands.add_parser('send', help='Explicitly request Wi-Fi delivery through the USB control connection')
    send.add_argument('--port', required=True)
    send.add_argument('--type', choices=('batch', 'csv', 'template'), required=True)
    send.add_argument('--id', help='Existing batch UUID or occupied template slot; omitted for CSV')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            folder = args.out_dir or PRIVATE_ROOT / 'fingerprint-wifi' / args.device
            device_file, receiver_file = initialize(folder.resolve(), args.host, args.port, args.device,
                args.scanner_id, args.gallery_id, args.compatibility_group, input('Wi-Fi SSID: '),
                getpass.getpass('Wi-Fi password (hidden): '), args.openssl)
            print(f'Private files created: {device_file}; {receiver_file}. Keep these private.')
        elif args.command == 'receive':
            config = validate_receiver_config(private_json(args.config), args.config.resolve().parent)
            ipaddress.IPv4Address(args.bind)
            return serve(config, args.bind, args.once)
        else:
            with connect(args.port) as port:
                if args.command == 'provision':
                    provision(port, private_json(args.config))
                    print('Wi-Fi configuration and TLS clock confirmed. Originals retained; capture remains stopped.')
                elif args.command == 'status':
                    port.write(b'w status\n')
                    print(wait_status(port, 'FPWSTATUS ', time.monotonic() + 15))
                elif args.command == 'forget':
                    port.write(b'w forget\n')
                    if wait_status(port, 'FPWFORGOTTEN', time.monotonic()+15) != 'FPWFORGOTTEN':
                        raise ValueError('Wi-Fi credential removal not confirmed')
                    print('Wi-Fi credentials removed. Capture and enrollment files retained.')
                elif args.command == 'clock':
                    set_clock(port)
                    print('TLS clock set from laptop. Attendance RTC and saved timestamps unchanged.')
                else:
                    identifier = args.id
                    if args.type == 'batch':
                        exact_uuid(identifier)
                    elif args.type == 'template':
                        if not identifier or not SLOT.fullmatch(identifier) or int(identifier) > 65534:
                            raise ValueError('Use --id with an occupied numeric template slot')
                    elif identifier is not None:
                        raise ValueError('CSV send has no --id argument')
                    suffix = '' if args.type == 'csv' else ' ' + identifier
                    port.write(f'w send {args.type}{suffix}\n'.encode('ascii'))
                    wait_status(port, 'FPWSAVED ', time.monotonic()+330)
                    print('Confirmed laptop receipt only. Website import is separate; device files retained.')
    except TransferCancelled:
        print('Wi-Fi transfer cancelled. Device files retained; laptop receipt remains unconfirmed.')
        return 1
    except KeyboardInterrupt:
        print('Stopped. Preserve originals and retry any unconfirmed transfer.')
        return 1
    except (OSError, ValueError, TypeError, KeyError, EOFError, subprocess.SubprocessError):
        # Never reflect a private config, token, payload or arbitrary network error text.
        parser.exit(1, 'Wi-Fi operation failed. Check private configuration, port/network/certificate and local device status. Originals retained.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
