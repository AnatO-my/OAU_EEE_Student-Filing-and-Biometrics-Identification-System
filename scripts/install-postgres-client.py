"""Fetch compatible Windows client DLLs from EDB; no server or system installation.

Only bounded HTTP ranges for the ZIP directory and seven client DLLs are fetched.
Run from any directory with the project's Python interpreter.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import urllib.request
import zipfile
import zlib


ARCHIVE_URL = "https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip"
DESTINATION = Path(__file__).resolve().parents[1] / "private-data" / "aiven" / "pg-client16" / "bin"
LIBRARIES = (
    "libcrypto-3-x64.dll", "libiconv-2.dll", "libintl-9.dll", "libpq.dll",
    "libssl-3-x64.dll", "libwinpthread-1.dll", "zlib1.dll",
)


class RemoteArchive(io.RawIOBase):
    """Seekable ZIP input that refuses responses containing the full archive."""

    def __init__(self):
        with urllib.request.urlopen(urllib.request.Request(ARCHIVE_URL, method="HEAD"), timeout=30) as response:
            self.size = int(response.headers["Content-Length"])
        self.position = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def read(self, count=-1):
        count = self.size - self.position if count < 0 else min(count, self.size - self.position)
        if count <= 0:
            return b""
        if count > 16 * 1024 * 1024:
            raise ValueError("Refusing an archive range larger than 16 MiB")
        end = self.position + count - 1
        request = urllib.request.Request(ARCHIVE_URL, headers={"Range": f"bytes={self.position}-{end}"})
        with urllib.request.urlopen(request, timeout=60) as response:
            expected_range = f"bytes {self.position}-{end}/{self.size}"
            if response.status != 206 or response.headers.get("Content-Range") != expected_range:
                raise RuntimeError("The download server did not honor the bounded HTTP range")
            data = response.read(count + 1)
        if len(data) != count:
            raise RuntimeError("Incomplete client archive range; run the helper again")
        self.position += count
        return data


def main():
    if os.name != "nt":
        raise SystemExit("This helper is for Windows x64 development; other platforms use the pinned psycopg binary package.")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {"version": "16.15", "source": ARCHIVE_URL, "sha256": {}}
    with RemoteArchive() as remote, zipfile.ZipFile(remote) as archive:
        for name in LIBRARIES:
            entry = archive.getinfo("pgsql/bin/" + name)
            target = DESTINATION / name
            data = target.read_bytes() if target.is_file() else b""
            if len(data) != entry.file_size or zlib.crc32(data) != entry.CRC:
                print(f"Downloading PostgreSQL client library: {name}", flush=True)
                data = archive.read(entry)  # ZIP member CRC is verified here.
                if not data.startswith(b"MZ"):
                    raise RuntimeError("Archive entry is not a Windows library")
                temporary = target.with_suffix(".dll.download")
                temporary.write_bytes(data)
                temporary.replace(target)
            else:
                print(f"Verified existing client library: {name}", flush=True)
            manifest["sha256"][name] = hashlib.sha256(data).hexdigest()
    (DESTINATION.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Windows PostgreSQL 16.15 client ready in private-data/aiven/pg-client16/bin.")
    print("No database server or Windows service was installed. No database connection was opened.")


if __name__ == "__main__":
    main()
