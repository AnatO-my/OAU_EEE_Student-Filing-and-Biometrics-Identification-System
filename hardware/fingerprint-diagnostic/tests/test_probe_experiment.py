import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import probe_experiment as probe

SCANNER="22222222-2222-4222-8222-222222222222"
DATA=bytes(range(64))
SOURCE={"capacity":162,"security_level":3,"packet_bytes":128,"system_id":0,"device_address":"FFFFFFFF"}

class Port:
    def __init__(self, lines):
        self.lines=[(line+"\n").encode() for line in lines]
        self.writes=[]
    def readline(self, limit):
        return self.lines.pop(0) if self.lines else b""
    def write(self, value): self.writes.append(value)
    def flush(self): pass

class ProbeTests(unittest.TestCase):
    def record(self): return probe.probe_record(DATA,SOURCE,SCANNER,"unit-1")

    def test_capture_transcript_and_record_round_trip(self):
        port=Port(["Lift your finger completely.", "Finger removed.", "Place a finger on the scanner.", "FPPROBE 1 162 3 128 0 FFFFFFFF", "FPDATA "+DATA[:32].hex(),
                   "FPDATA "+DATA[32:].hex(),f"FPEND 64 {zlib.crc32(DATA):08X}"])
        data,source=probe.receive_probe(port,time.monotonic()+1)
        self.assertEqual((data,source),(DATA,SOURCE))
        record=probe.probe_record(data,source,SCANNER,"unit-1")
        self.assertEqual(probe.validate_probe(record),DATA)
        self.assertNotIn("student_id",record)
        self.assertNotIn("slot_id",record["source"])

    def test_corrupt_or_truncated_export_has_no_valid_probe(self):
        for ending in ["FPEND 64 00000000","FPEND 63 00000000","FPERROR failed"]:
            with self.assertRaises(ValueError):
                probe.receive_probe(Port(["FPPROBE 1 162 3 128 0 FFFFFFFF",
                    "FPDATA "+DATA[:32].hex(),"FPDATA "+DATA[32:].hex(),ending]),time.monotonic()+1)

    def test_record_tampering_and_enrollment_files_rejected(self):
        for field,value in [("sha256","0"*64),("byte_length",65),("kind","enrollment"),
                            ("probe_format","as608-ef01-opaque"),("schema_version",True)]:
            record=self.record(); record[field]=value
            with self.assertRaises(ValueError): probe.validate_probe(record)

    def test_compare_saved_bytes_only_and_explicit_no_match(self):
        for result,score in [("MATCH",100),("NO_MATCH",0)]:
            port=Port(["FPPROBEREADY 1 64 3 0 FFFFFFFF",f"FPPROBERESULT 1 {result} {score}"])
            with patch.object(probe.time,"sleep"):
                report=probe.compare_probe(port,DATA,SOURCE,1,time.monotonic()+1)
            self.assertEqual(report["result"],result)
            self.assertEqual(port.writes[0],f"j 1 64 {zlib.crc32(DATA):08X}\n".encode())
            self.assertEqual(bytes.fromhex(b"".join(port.writes[1:]).decode()),DATA)
            self.assertTrue(all(not entry.startswith(b"u ") for entry in port.writes))

    def test_mismatched_security_sends_no_probe_bytes(self):
        port=Port(["FPPROBEREADY 1 64 4 0 FFFFFFFF"])
        with self.assertRaises(ValueError): probe.compare_probe(port,DATA,SOURCE,1,time.monotonic()+1)
        self.assertEqual(len(port.writes),1)

    def test_bad_result_not_reported_as_success(self):
        for line in ["FPPROBERESULT 2 MATCH 100","FPPROBERESULT 1 NO_MATCH 12",
                     "FPPROBERESULT 1 MATCH 999999","FPERROR bad readback"]:
            with patch.object(probe.time,"sleep"), self.assertRaises(ValueError):
                probe.compare_probe(Port(["FPPROBEREADY 1 64 3 0 FFFFFFFF",line]),DATA,SOURCE,1,time.monotonic()+1)

    def test_private_file_round_trip_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"probe.json"
            probe.save_new(path,self.record())
            _,data=probe.read_probe(path)
            self.assertEqual(data,DATA)
            with self.assertRaises(FileExistsError): probe.save_new(path,self.record())

    def test_timeout_and_oversized_inputs_fail(self):
        with self.assertRaises(TimeoutError): probe.receive_probe(Port([]),time.monotonic()-1)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"large.json"; path.write_text("x"*16385)
            with self.assertRaises(ValueError): probe.read_probe(path)

    def test_direct_comparison_has_distinct_command_and_markers(self):
        port=Port(["FPPROBEDIRECTREADY 1 64 3 0 FFFFFFFF", "FPPROBEDIRECTRESULT 1 MATCH 172"])
        with patch.object(probe.time,"sleep"):
            result=probe.compare_probe(port,DATA,SOURCE,1,time.monotonic()+1,method="direct")
        self.assertEqual(result["raw_score"],172)
        self.assertEqual(result["method"],"direct")
        self.assertTrue(port.writes[0].startswith(b"k "))

    def test_no_match_has_no_measured_score(self):
        port=Port(["FPPROBEREADY 1 64 3 0 FFFFFFFF", "FPPROBERESULT 1 NO_MATCH 0"])
        with patch.object(probe.time,"sleep"):
            result=probe.compare_probe(port,DATA,SOURCE,1,time.monotonic()+1)
        self.assertIsNone(result["raw_score"])

if __name__=="__main__": unittest.main()
