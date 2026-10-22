"""Safety boundaries; the separate drill supplies real PostgreSQL evidence."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from postgres_backup import backup, connection_options, process_environment, restore_verify


class BackupSafetyTests(unittest.TestCase):
    def test_restore_refuses_aiven_before_reading_an_archive_or_connecting(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            restore_verify(Path("unused"), {"host": "example.aivencloud.com"}, Path("absent.dump"))

    def test_local_source_refuses_a_remote_address(self):
        with patch.dict(os.environ, {"POSTGRES_HOST": "example.aivencloud.com"}, clear=True):
            with self.assertRaisesRegex(ValueError, "loopback"):
                connection_options(local=True)

    def test_hosted_backup_refuses_weaker_tls(self):
        with patch.dict(os.environ, {"POSTGRES_HOST": "example.aivencloud.com", "POSTGRES_SSLMODE": "require"}, clear=True):
            with self.assertRaisesRegex(ValueError, "verify-full"):
                connection_options()

    def test_child_ignores_inherited_hostaddr_and_password_files(self):
        with patch.dict(os.environ, {"PGHOSTADDR": "203.0.113.1", "PGSERVICE": "unsafe",
                                     "PGPASSFILE": "saved-passwords", "PGOPTIONS": "-c search_path=other"}, clear=True):
            env = process_environment({"host": "127.0.0.1", "user": "synthetic", "password": "synthetic"}, "synthetic")
        self.assertNotIn("PGHOSTADDR", env)
        self.assertNotIn("PGSERVICE", env)
        self.assertNotIn("PGOPTIONS", env)
        self.assertEqual(env["PGPASSFILE"], os.devnull)

    def test_backup_preserves_existing_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.dump"
            partial = path.with_suffix(".dump.partial")
            partial.write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError, "already exists"):
                backup(Path("unused"), {}, "unused", path)
            self.assertEqual(partial.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
