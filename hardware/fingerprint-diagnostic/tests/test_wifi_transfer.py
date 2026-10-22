"""Synthetic serial, file, and loopback TLS tests; no devices or website writes."""
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import shutil
import socket
import ssl
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import wifi_transfer as wifi
from portable_template import read_record
from test_deferred_batches import IDS, wire

TOKEN = 'a' * 64


def config(root):
    return dict(output_dir=Path(root), devices=[dict(device_uuid=IDS[0], token=TOKEN,
        scanner_id=IDS[3], gallery_id=IDS[5], compatibility_group='as608-unit-1')])


def request(kind, identifier, token=TOKEN, device=IDS[0]):
    return f'FPWIFI 1 {token} {device} {kind} {identifier}\n'.encode('ascii')


def file_wire(kind, data):
    digest = hashlib.sha256(data).hexdigest()
    return (f'FPFILE 1 {kind} {len(data)} {digest}\n'.encode()
        + b''.join(b'FPDATA ' + data[i:i+32].hex().upper().encode() + b'\n' for i in range(0, len(data), 32))
        + f'FPFILEEND {len(data)} {digest}\n'.encode())


def csv_data(device=IDS[2]):
    return wifi.CSV_HEADER + f'{IDS[4]},{device},2026-10-21T10:30:00,1,{"f"*64},80\n'.encode()


def template_data():
    return b'FPT1' + struct.pack('>HHHHHI', 1, 150, 3, 128, 0, 0xFFFFFFFF) + b'synthetic-template-only'


class SerialPort(io.BytesIO):
    def __init__(self, source):
        super().__init__(source)
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        return len(data)


class ReceiverTests(unittest.TestCase):
    def test_device_cancellation_status_is_handled_immediately(self):
        with self.assertRaises(wifi.TransferCancelled):
            wifi.wait_status(io.BytesIO(b'FPWCANCELLED transfer cancelled; files retained\n'),
                             'FPWSAVED ', time.monotonic()+330)

    def test_batch_validates_and_receipt_binds_both_digests(self):
        with tempfile.TemporaryDirectory() as root:
            responses = []
            result = wifi.handle_transfer(io.BytesIO(request('batch', IDS[1])+wire().getvalue()), responses.append, config(root))
            self.assertEqual(responses, [b'FPWREADY 1\n', result.receipt()])
            self.assertEqual(result.count, 1)
            self.assertEqual(result.file_sha256, hashlib.sha256(result.path.read_bytes()).hexdigest())
            binary_digest = wire().getvalue().splitlines()[-1].split()[-1].decode()
            self.assertEqual(result.wire_sha256, hashlib.sha256((binary_digest+':0').encode()).hexdigest())
            self.assertEqual(wifi.batches.validate_file(result.path.read_bytes())[1], 1)

    def test_changed_pending_flag_preserves_both_snapshots(self):
        with tempfile.TemporaryDirectory() as root:
            snapshots = [wifi.handle_transfer(io.BytesIO(request('batch', IDS[1])+wire(pending=pending).getvalue()),
                         lambda _: None, config(root)) for pending in (False, True)]
            self.assertNotEqual(snapshots[0].wire_sha256, snapshots[1].wire_sha256)
            self.assertNotEqual(snapshots[0].path, snapshots[1].path)
            self.assertTrue(all(item.path.exists() for item in snapshots))

    def test_rejected_auth_or_identifier_never_accepts_payload(self):
        cases = [request('csv', 'attendance', token='b'*64), request('csv', 'attendance', device=IDS[1]),
                 request('batch', '../escape'), request('template', '01'), request('template', '65535'),
                 request('csv', '../../file'), request('unknown', 'attendance'), b'x'*256+b'\n']
        for raw in cases:
            with self.subTest(size=len(raw)), tempfile.TemporaryDirectory() as root:
                responses = []
                with self.assertRaises((ValueError, TimeoutError)):
                    wifi.handle_transfer(io.BytesIO(raw), responses.append, config(root), deadline=time.monotonic()+0.02)
                self.assertEqual(responses, [])
                self.assertEqual(list(Path(root).rglob('*')), [])

    def test_batch_commissioning_mismatch_never_receipted(self):
        for key, value in [('scanner_id', IDS[1]), ('compatibility_group', 'other')]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                settings = config(root); settings['devices'][0][key] = value
                responses = []
                with self.assertRaises(ValueError):
                    wifi.handle_transfer(io.BytesIO(request('batch', IDS[1])+wire().getvalue()), responses.append, settings)
                self.assertEqual(responses, [b'FPWREADY 1\n'])
                self.assertEqual(list(Path(root).rglob('*.jsonl')), [])

    def test_csv_preserves_legacy_origin_and_retries_without_overwriting(self):
        data = csv_data()
        with tempfile.TemporaryDirectory() as root:
            results = [wifi.handle_transfer(io.BytesIO(request('csv', 'attendance')+file_wire('csv', data)),
                       lambda _: None, config(root)) for _ in range(2)]
            self.assertEqual(results[0].receipt(), results[1].receipt())
            self.assertEqual(results[0].path.read_bytes(), data)
            self.assertEqual(results[0].count, 1)
            self.assertNotEqual(IDS[2], IDS[0])
            self.assertEqual(len(list(Path(root).rglob('*.csv'))), 1)

    def test_csv_rejects_invalid_dates_identity_duplicate_fields_and_values(self):
        original = csv_data()
        variants = [original[:-1], original.replace(b'2026-10-21', b'2026-02-30'),
                    original.replace(b'10:30:00', b'24:30:00'), original.replace(b',80\n', b',65536\n'),
                    original.replace(b',1,', b',-1,'), original.replace(b',1,', b',=1,'),
                    original+original.splitlines(keepends=True)[1], original.replace(b'\n', b'\r\n'),
                    original.replace(IDS[4].encode(), b'00000000-0000-0000-0000-000000000000'),
                    original.replace(b'f'*64, b'F'*64), original+b'\n', original.replace(b',80\n', b',80,extra\n')]
        for value in variants:
            with self.subTest(value_size=len(value)), self.assertRaises(ValueError):
                wifi.validate_csv(value)
        other = original + csv_data(IDS[3]).splitlines(keepends=True)[1].replace(IDS[4].encode(), IDS[5].encode())
        with self.assertRaises(ValueError):
            wifi.validate_csv(other)
        self.assertEqual(wifi.validate_csv(wifi.CSV_HEADER), 0)

    def test_template_saved_as_unassigned_restorable_record_with_stable_retry(self):
        with tempfile.TemporaryDirectory() as root:
            results = [wifi.handle_transfer(io.BytesIO(request('template', '1')+file_wire('template', template_data())),
                       lambda _: None, config(root)) for _ in range(2)]
            self.assertEqual(results[0].receipt(), results[1].receipt())
            record = read_record(results[0].path)
            self.assertIsNone(record.student_id)
            self.assertEqual(record.validated_bytes(), b'synthetic-template-only')
            self.assertEqual(record.source['scanner_id'], IDS[3])
            self.assertEqual(record.source['gallery_id'], IDS[5])
            self.assertEqual(record.source['slot_id'], 1)
            self.assertEqual(results[0].count, 1)

    def test_template_rejects_wrong_slot_parameters_and_empty_payload(self):
        data = template_data()
        for bad in (data[:18], data[:6]+b'\0\0'+data[8:], data[:10]+b'\0\x03'+data[12:], data+b'x'*2048):
            with self.assertRaises(ValueError):
                wifi.decode_template(bad, '1')
        with self.assertRaises(ValueError):
            wifi.decode_template(data, '2')

    def test_truncated_corrupt_oversized_or_wrong_type_has_no_success_receipt(self):
        raw = file_wire('csv', csv_data())
        cases = [raw[:-12], raw.replace(b'FPFILEEND ', b'FPFILEBAD '), raw.replace(b'FPDATA ', b'FPDATA ZZ', 1),
                 raw.replace(b'FPFILE 1 csv ', b'FPFILE 1 template ', 1),
                 f'FPFILE 1 csv {wifi.MAX_CSV_BYTES+1} {"a"*64}\n'.encode(),
                 raw.replace(b'4650', b'4750', 1)]
        cases[-1] = raw.replace(b'6576656E', b'6576656F', 1)
        for payload in cases:
            with self.subTest(size=len(payload)), tempfile.TemporaryDirectory() as root:
                responses = []
                with self.assertRaises((ValueError, TimeoutError)):
                    wifi.handle_transfer(io.BytesIO(request('csv', 'attendance')+payload), responses.append,
                                         config(root), deadline=time.monotonic()+0.03)
                self.assertEqual(responses, [b'FPWREADY 1\n'])
                self.assertEqual(list(Path(root).rglob('*.csv')), [])

    def test_disk_flush_failure_retains_partial_and_never_receipts(self):
        with tempfile.TemporaryDirectory() as root:
            responses = []
            with patch.object(wifi.os, 'fsync', side_effect=OSError('synthetic disk failure')):
                with self.assertRaises(OSError):
                    wifi.handle_transfer(io.BytesIO(request('csv', 'attendance')+file_wire('csv', csv_data())),
                                         responses.append, config(root))
            self.assertEqual(responses, [b'FPWREADY 1\n'])
            self.assertEqual(len(list(Path(root).rglob('*.partial'))), 1)
            self.assertEqual(list(Path(root).rglob('*.csv')), [])

    def test_lost_receipt_retries_from_saved_original(self):
        with tempfile.TemporaryDirectory() as root:
            responses = []
            def disconnected(value):
                responses.append(value)
                if value.startswith(b'FPWRECEIPT'):
                    raise OSError('synthetic lost response')
            with self.assertRaises(OSError):
                wifi.handle_transfer(io.BytesIO(request('template', '1')+file_wire('template', template_data())),
                                     disconnected, config(root))
            result = wifi.handle_transfer(io.BytesIO(request('template', '1')+file_wire('template', template_data())),
                                          lambda _: None, config(root))
            self.assertEqual(responses[-1], result.receipt())
            self.assertEqual(len(list(Path(root).rglob('*.fpt.json'))), 1)

    def test_conflicting_existing_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root)/'saved.csv'
            original = csv_data()
            target.write_bytes(original)
            changed = original.replace(b',80\n', b',81\n')
            with self.assertRaises(ValueError):
                wifi.save_verified(target, changed, wifi.validate_csv)
            self.assertEqual(target.read_bytes(), original)


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL needed for synthetic TLS certificate tests')
class ConfigurationAndTlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.device_path, cls.receiver_path = wifi.initialize(cls.root/'setup', '127.0.0.1', 9443,
            IDS[0], IDS[3], IDS[5], 'as608-unit-1', 'synthetic-test-network', 'not-a-real-password')
        cls.device = wifi.private_json(cls.device_path)
        cls.receiver = wifi.validate_receiver_config(wifi.private_json(cls.receiver_path), cls.receiver_path.parent)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_private_configuration_and_firmware_payload_are_bounded(self):
        payload = wifi.validate_device_config(self.device)
        self.assertEqual(payload[:4], b'FPW1')
        self.assertEqual(struct.unpack('>H', payload[4:6])[0], 9443)
        self.assertEqual(len(payload[6:].split(b'\0')), 7)
        self.assertLessEqual(len(payload), 4096)
        self.assertEqual(self.device['certificate_sha256'], hashlib.sha256(
            ssl.PEM_cert_to_DER_cert(self.device['ca_pem'])).hexdigest())
        with self.assertRaises(FileExistsError):
            wifi.initialize(self.root/'setup', '127.0.0.1', 9443, IDS[0], IDS[3], IDS[5],
                            'as608-unit-1', 'synthetic-test-network', 'not-a-real-password')

    def test_invalid_config_pin_credential_fields_and_allowlist_rejected(self):
        changes = [('certificate_sha256', '0'*64), ('password', 'short'), ('ssid', 'bad\nnetwork'),
                   ('port', True), ('host', 'https://invalid'), ('token', 'A'*64), ('schema_version', True)]
        for key, value in changes:
            with self.subTest(key=key), self.assertRaises(ValueError):
                wifi.validate_device_config({**self.device, key:value})
        raw = wifi.private_json(self.receiver_path)
        for change in ({'devices': []}, {'devices': raw['devices']*2}, {'schema_version': True}):
            with self.assertRaises(ValueError):
                wifi.validate_receiver_config({**raw, **change}, self.receiver_path.parent)

    def test_provision_verifies_device_and_complete_receipts(self):
        payload = wifi.validate_device_config(self.device)
        source = (f'FPWSTATUS 1 {IDS[0]} 0 0\nFPWREADY {len(payload)}\n'
                  'FPWCONFIGURED\nFPWCLOCK\n').encode()
        port = SerialPort(source)
        with patch.object(wifi.time, 'sleep'):
            wifi.provision(port, self.device)
        self.assertEqual(port.writes[0], b'w status\n')
        self.assertEqual(port.writes[1], f'w configure {len(payload)} {hashlib.sha256(payload).hexdigest()}\n'.encode())
        self.assertEqual(b''.join(port.writes[2:-1]), payload)
        wrong = SerialPort(f'FPWSTATUS 1 {IDS[1]} 0 0\n'.encode())
        with self.assertRaises(ValueError):
            wifi.provision(wrong, self.device)
        self.assertEqual(wrong.writes, [b'w status\n'])

    def loopback(self, callback):
        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(5)
        outcomes = []
        with tempfile.TemporaryDirectory() as directory:
            settings = {**self.receiver, 'output_dir': Path(directory)}
            def server():
                try:
                    connection, _ = listener.accept(); connection.settimeout(3)
                    with wifi.tls_context(settings).wrap_socket(connection, server_side=True) as secure:
                        reader = wifi.DeadlineReader(secure, time.monotonic()+5)
                        try:
                            outcomes.append(wifi.handle_transfer(reader, secure.sendall, settings))
                        finally:
                            reader.close()
                except Exception as exc:
                    outcomes.append(type(exc))
                finally:
                    listener.close()
            thread = threading.Thread(target=server, daemon=True); thread.start()
            try:
                callback(listener.getsockname())
            finally:
                thread.join(8)
            self.assertFalse(thread.is_alive())
            return outcomes

    def test_real_loopback_tls_and_all_three_types(self):
        for kind, identifier, payload in [('batch', IDS[1], wire().getvalue()),
                ('csv', 'attendance', file_wire('csv', csv_data())),
                ('template', '1', file_wire('template', template_data()))]:
            receipts = []
            def client(address):
                context = ssl.create_default_context(cadata=self.device['ca_pem'])
                with context.wrap_socket(socket.create_connection(address, timeout=3), server_hostname='127.0.0.1') as secure:
                    self.assertEqual(hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest(), self.device['certificate_sha256'])
                    names = secure.getpeercert()['subjectAltName']
                    self.assertIn(('IP Address', '127.0.0.1'), names)
                    self.assertIn(('DNS', '127.0.0.1'), names)
                    secure.sendall(request(kind, identifier, token=self.device['token']))
                    stream = secure.makefile('rb')
                    self.assertEqual(stream.readline(), b'FPWREADY 1\n')
                    secure.sendall(payload)
                    receipts.append(stream.readline())
                    stream.close()
            outcomes = self.loopback(client)
            self.assertEqual(len(outcomes), 1)
            self.assertIsInstance(outcomes[0], wifi.SavedTransfer)
            self.assertEqual(receipts, [outcomes[0].receipt()])

    def test_wrong_hostname_and_untrusted_cert_are_rejected_by_tls(self):
        for trusted, hostname in [(True, 'wrong.invalid'), (False, '127.0.0.1')]:
            def client(address):
                context = ssl.create_default_context(cadata=self.device['ca_pem']) if trusted else ssl.create_default_context()
                with self.assertRaises(ssl.SSLCertVerificationError):
                    with context.wrap_socket(socket.create_connection(address, timeout=3), server_hostname=hostname):
                        pass
            outcomes = self.loopback(client)
            self.assertEqual(len(outcomes), 1)
            # Windows can report a reset instead of a TLS alert after the
            # client has already rejected the certificate above.
            self.assertIn(outcomes[0], (ssl.SSLError, ConnectionResetError))

    def test_plaintext_peer_does_not_reach_file_handler(self):
        def client(address):
            with socket.create_connection(address, timeout=3) as connection:
                connection.sendall(b'GET / HTTP/1.0\r\n\r\n')
        outcomes = self.loopback(client)
        self.assertEqual(len(outcomes), 1)
        self.assertIn(outcomes[0], (ssl.SSLError, ConnectionResetError))


if __name__ == '__main__':
    unittest.main()
