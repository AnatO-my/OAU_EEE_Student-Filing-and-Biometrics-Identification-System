"""Fetch an isolated Windows PostgreSQL runtime from the official EDB archive.

No Windows service is installed. Only server/client binaries, shared catalog
files, and their libraries are extracted under ignored private-data/. HTTP
ranges avoid downloading pgAdmin. ZIP CRCs and a local SHA-256 manifest detect
corruption; authenticity relies on HTTPS to the publisher (not the ZIP CRC).
"""

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
URL = "https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip"
PROGRAMS = {"initdb.exe", "pg_ctl.exe", "postgres.exe", "pg_dump.exe", "pg_restore.exe",
            "createdb.exe", "dropdb.exe", "psql.exe", "pg_isready.exe"}


def selected(name):
    if name.endswith("/"):
        return False
    if name.startswith("pgsql/share/"):
        return True
    if name.startswith("pgsql/lib/") and name.count("/") == 2:
        return name.endswith(".dll")
    if name.startswith("pgsql/bin/") and name.count("/") == 2:
        basename = name.rsplit("/", 1)[1]
        return basename in PROGRAMS or (basename.endswith(".dll") and not basename.startswith("wx"))
    return name == "pgsql/server_license.txt" or name == "pgsql/commandlinetools_3rd_party_licenses.txt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "private-data" / "postgres18")
    parser.add_argument("--aiven-client", action="store_true", help="Also pair pg_dump 18.6 with the verified libpq 16.15 Aiven client")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This archive contains Windows x64 binaries.")
    destination = args.destination.resolve()
    # Reuse the bounded publisher download transport already used for the client.
    spec = importlib.util.spec_from_file_location("client_download", ROOT / "scripts/install-postgres-client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ARCHIVE_URL = URL
    with module.RemoteArchive() as remote, zipfile.ZipFile(remote) as archive:
        entries = [entry for entry in archive.infolist() if selected(entry.filename)]
        missing = []
        for entry in entries:
            target = destination / Path(entry.filename).relative_to("pgsql")
            data = target.read_bytes() if target.is_file() else b""
            if len(data) != entry.file_size or zlib.crc32(data) != entry.CRC:
                missing.append(entry)
        # Coalesce nearby members to avoid one network request per catalog file.
        groups = []
        for entry in sorted(missing, key=lambda entry: entry.header_offset):
            start, end = entry.header_offset, entry.header_offset + entry.compress_size + 4096
            if groups and start - groups[-1][1] < 65536 and end - groups[-1][0] < 16 * 1024 * 1024:
                groups[-1][1] = end
                groups[-1][2].append(entry)
            else:
                groups.append([start, end, [entry]])
        for index, (start, end, members) in enumerate(groups, 1):
            end = min(end, remote.size)
            remote.seek(start)
            payload = remote.read(end - start)
            print(f"Publisher range {index}/{len(groups)}: {len(payload) / 1048576:.2f} MiB, {len(members)} files", flush=True)
            # A seekable window gives ZipFile normal extraction and CRC checking.
            class Window(io.BytesIO):
                def seek(self, offset, whence=0):
                    if whence == 0:
                        offset -= start
                    return super().seek(offset, whence) + start

                def tell(self):
                    return super().tell() + start

            original = archive.fp
            archive.fp = Window(payload)
            try:
                for entry in members:
                    data = archive.read(entry)
                    relative = Path(entry.filename).relative_to("pgsql")
                    if ".." in relative.parts:
                        raise RuntimeError("Unsafe archive path")
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(target.name + ".download")
                    temporary.write_bytes(data)
                    temporary.replace(target)
            finally:
                archive.fp.close()
                archive.fp = original
        manifest = {"version": "18.6", "source": URL, "sha256": {}}
        for entry in entries:
            relative = Path(entry.filename).relative_to("pgsql")
            manifest["sha256"][relative.as_posix()] = hashlib.sha256((destination / relative).read_bytes()).hexdigest()
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Isolated PostgreSQL 18.6 runtime ready: {destination}")
    print("No service was installed and no database was opened.")
    if args.aiven_client:
        compatible = ROOT / "private-data" / "aiven" / "pg-client16"
        client_manifest = json.loads((compatible / "manifest.json").read_text(encoding="utf-8"))
        if client_manifest["version"] != "16.15":
            raise RuntimeError("Run scripts/install-postgres-client.py for the verified PostgreSQL 16.15 client first")
        client_destination = ROOT / "private-data" / "postgres18-aiven-client" / "bin"
        client_destination.mkdir(parents=True, exist_ok=True)
        for name, expected in client_manifest["sha256"].items():
            source = compatible / "bin" / name
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise RuntimeError("Compatible client library checksum mismatch")
            shutil.copy2(source, client_destination / name)
        # These current server-major utilities are required to dump PostgreSQL
        # 18; libpq's backward-compatible public ABI supplies the TLS transport.
        # Keep this client separate so server DLLs remain the publisher's set.
        for name in ("pg_dump.exe", "pg_restore.exe"):
            shutil.copy2(destination / "bin" / name, client_destination / name)
        # Compression dependencies must match the current utility build.
        for name in ("liblz4.dll", "libzstd.dll"):
            shutil.copy2(destination / "bin" / name, client_destination / name)
        for name in ("pg_dump.exe", "pg_restore.exe"):
            result = subprocess.run([str(client_destination / name), "--version"], capture_output=True,
                                    text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print(result.stdout.strip())
        print(f"Aiven backup utilities with compatible TLS transport ready: {client_destination}")


if __name__ == "__main__":
    main()
