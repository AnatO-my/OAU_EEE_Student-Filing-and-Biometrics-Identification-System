import base64
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import uuid
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import deferred_batches as batch

IDS = [str(uuid.UUID(int=i)) for i in range(1, 7)]


def sealed(data):
    return data + struct.pack('>I', zlib.crc32(data))


def header():
    return sealed(b'FPB1' + b''.join(uuid.UUID(value).bytes for value in IDS[:4])
                  + b'as608-unit-1'.ljust(80, b'\0') + struct.pack('>HHHHI', 150, 3, 128, 0, 0xFFFFFFFF))


def event(identifier=IDS[4], uptime=123456, probe=b'only-synthetic-data'):
    return sealed(b'FPE1' + uuid.UUID(identifier).bytes + uuid.UUID(IDS[5]).bytes
                  + struct.pack('>QH', uptime, len(probe)) + probe)


def block(kind, data):
    crc = zlib.crc32(data)
    return (f'FPBLOCK {kind} {len(data)} {crc:08X}\n'
            + ''.join('FPDATA ' + data[i:i+32].hex().upper() + '\n' for i in range(0, len(data), 32))
            + f'FPEND {len(data)} {crc:08X}\n')


def wire(events=None, pending=False):
    events = events if events is not None else [event()]
    raw_header = header()
    digest = hashlib.sha256(raw_header + b''.join(events)).hexdigest()
    return io.BytesIO((f'FPBATCH 1 {len(events)} {int(pending)}\n' + block('header', raw_header)
                       + ''.join(block('event', value) for value in events)
                       + f'FPBATCHEND {len(events)} {digest}\n').encode('ascii'))


def received(port=None):
    return batch.receive_batch(port or wire(), IDS[1], __import__('time').monotonic() + 0.2)


class BatchTests(unittest.TestCase):
    def test_roundtrip_and_no_invented_identity_or_wall_time(self):
        data = received()
        metadata, count = batch.validate_file(data)
        record = json.loads(data.splitlines()[1])
        self.assertEqual(count, 1)
        self.assertEqual(metadata['class_session_uuid'], IDS[2])
        self.assertFalse(metadata['clock']['wall_clock_verified'])
        self.assertIsNone(record['captured_at'])
        self.assertNotIn('student_id', record)
        self.assertEqual(base64.b64decode(record['probe_base64']), b'only-synthetic-data')

    def test_empty_batch_and_pending_tail_remain_explicit(self):
        for events in ([], [event()]):
            data = received(wire(events, pending=True))
            metadata, count = batch.validate_file(data)
            self.assertTrue(metadata['interrupted_write_pending'])
            self.assertEqual(count, len(events))

    def test_wrong_batch_rejected(self):
        with self.assertRaises(ValueError):
            batch.receive_batch(wire(), IDS[0], __import__('time').monotonic() + 1)

    def test_corruption_truncation_and_bad_digest_rejected(self):
        original = wire().getvalue()
        variants = [original.replace(b'46504231', b'47504231', 1), original[:-20],
                    original.replace(b'FPBATCHEND 1 ', b'FPBATCHEND 2 '),
                    original.replace(b'FPDATA ', b'FPDATA Z', 1)]
        for value in variants:
            with self.subTest(size=len(value)), self.assertRaises((ValueError, TimeoutError)):
                received(io.BytesIO(value))

    def test_duplicate_event_and_backwards_elapsed_time_rejected(self):
        for events in ([event(), event()], [event(uptime=100), event(identifier=IDS[0], uptime=99)]):
            with self.assertRaises(ValueError):
                received(wire(events))

    def test_new_boot_can_restart_elapsed_time(self):
        second = bytearray(event(identifier=IDS[0], uptime=1))
        second[20:36] = uuid.UUID(IDS[3]).bytes
        second[-4:] = struct.pack('>I', zlib.crc32(second[:-4]))
        self.assertEqual(batch.validate_file(received(wire([event(), bytes(second)])))[1], 2)

    def test_oversize_and_invalid_persistent_records(self):
        for value in (header()[:-1], sealed(b'FPB1' + header()[4:-5]), event(probe=b''), event(probe=b'x' * 2049)):
            with self.assertRaises(ValueError):
                (batch.decode_header if value[:4] == b'FPB1' else batch.decode_event)(value)
        with self.assertRaises(ValueError):
            received(io.BytesIO(b'FPBATCH 1 513 0\n'))

    def test_invalid_uuid_and_group_padding_rejected(self):
        raw = bytearray(header())
        raw[4:20] = b'\0' * 16
        with self.assertRaises(ValueError):
            batch.decode_header(sealed(bytes(raw[:-4])))
        raw = bytearray(header()); raw[100] = 1
        with self.assertRaises(ValueError):
            batch.decode_header(sealed(bytes(raw[:-4])))

    def test_existing_download_never_overwritten(self):
        data = received()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.jsonl'
            batch.save_download(path, data)
            self.assertEqual(path.read_bytes(), data)
            with self.assertRaises(FileExistsError):
                batch.save_download(path, data)
            self.assertEqual(path.read_bytes(), data)

    def test_edit_or_missing_trailer_rejected_before_save(self):
        data = received()
        for value in (data.replace(b'123456', b'123457'), b'\n'.join(data.splitlines()[:-1]) + b'\n'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'capture.jsonl'
                with self.assertRaises(ValueError):
                    batch.save_download(path, value)
                self.assertFalse(path.exists())

    def test_device_error_is_not_a_valid_empty_export(self):
        with self.assertRaises(ValueError):
            received(io.BytesIO(b'FPBERROR storage unavailable\n'))

    def test_long_sdk_status_is_bounded_and_data_frames_stay_strict(self):
        port = io.BytesIO(b'[SDK] ' + b'x' * 300 + b'\nFPBINITIALIZED ready\n')
        self.assertEqual(batch.wait(port, 'FPBINITIALIZED ', __import__('time').monotonic()+1), 'FPBINITIALIZED ready')
        for raw in (b'x'*4096+b'\n', b'FPBINITIALIZED '+b'x'*300+b'\n'):
            with self.assertRaises(ValueError):
                batch.status_line(io.BytesIO(raw), __import__('time').monotonic()+1)


if __name__ == '__main__':
    unittest.main()
