"""Portable application backup and isolated loopback restore verification.

Credentials come from the current process environment or a hidden prompt, never
command arguments or a password file. A restore always creates a new randomly
named database on loopback and drops only that database when verification ends.
"""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def connection_options(prefix="POSTGRES_", local=False):
    host = os.environ.get(prefix + "HOST", "127.0.0.1" if local else "")
    if not host:
        raise ValueError(f"Set {prefix}HOST in the current terminal.")
    if local and host not in {"127.0.0.1", "::1"}:
        raise ValueError("Restore verification accepts only a literal loopback target address.")
    mode = os.environ.get(prefix + "SSLMODE", "disable" if local else "verify-full")
    if not local and mode != "verify-full":
        raise ValueError("Hosted backups require POSTGRES_SSLMODE=verify-full.")
    if local and mode != "disable":
        raise ValueError("The isolated loopback verification cluster must use SSLMODE=disable.")
    user = os.environ.get(prefix + "USER", "")
    if not user:
        raise ValueError(f"Set {prefix}USER in the current terminal.")
    password = os.environ.get(prefix + "PASSWORD")
    if not password:
        password = getpass.getpass(f"Database password for {user} (not saved): ")
    options = {"host": host, "port": os.environ.get(prefix + "PORT", "5432"),
               "user": user, "password": password, "sslmode": mode,
               "connect_timeout": 10, "gssencmode": "disable"}
    if not local:
        ca = os.environ.get(prefix + "SSLROOTCERT", "")
        if not ca or not Path(ca).is_file():
            raise ValueError("Set POSTGRES_SSLROOTCERT to the provider CA certificate.")
        options["sslrootcert"] = str(Path(ca).resolve())
    return options


def process_environment(options, database):
    # Ignore inherited service files, hostaddr overrides, options and default
    # password-file discovery. Only this invocation's explicit values apply.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    for key in ("host", "port", "user", "password", "sslmode", "sslrootcert", "connect_timeout", "gssencmode"):
        if key in options:
            env["PG" + key.upper()] = str(options[key])
    env.update(PGDATABASE=database, PGPASSFILE=os.devnull, PGAPPNAME="eee-backup-verification")
    return env


def run_program(pg_bin, program, arguments, options, database):
    executable = Path(pg_bin) / (program + (".exe" if os.name == "nt" else ""))
    if not executable.is_file():
        raise ValueError(f"Missing PostgreSQL utility: {executable}")
    result = subprocess.run([str(executable), *arguments], env=process_environment(options, database),
                            capture_output=True, text=True, encoding="utf-8", errors="replace", **FLAGS)
    if result.returncode:
        # Provider errors can include connection metadata. Do not echo them or
        # include environment values in exceptions/logs.
        raise RuntimeError(f"{program} failed (exit {result.returncode}). Check connectivity, TLS, client version and database permissions.")
    return result.stdout.strip()


def file_sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def fingerprint(conn):
    """Hash ordered table contents without storing application records."""
    conn.execute("SET LOCAL timezone = 'UTC'")
    conn.execute("SET LOCAL datestyle = 'ISO, YMD'")
    conn.execute("SET LOCAL extra_float_digits = 3")
    conn.execute("SET LOCAL bytea_output = 'hex'")
    tables = conn.execute("""
        SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE c.relkind IN ('r', 'p') AND n.nspname NOT LIKE 'pg_%'
          AND n.nspname <> 'information_schema' ORDER BY n.nspname, c.relname
    """).fetchall()
    result = {"tables": {}, "constraints": [], "sequences": {}}
    for schema, table in tables:
        relation = sql.Identifier(schema, table)
        count = conn.execute(sql.SQL("SELECT count(*) FROM {}").format(relation)).fetchone()[0]
        digest = hashlib.sha256()
        query = sql.SQL("COPY (SELECT row_to_json(r)::text FROM {} r ORDER BY row_to_json(r)::text COLLATE \"C\") TO STDOUT").format(relation)
        with conn.cursor().copy(query) as copy:
            for chunk in copy:
                digest.update(chunk)
        result["tables"][f"{schema}.{table}"] = {"rows": count, "sha256": digest.hexdigest()}
    result["constraints"] = [list(row) for row in conn.execute("""
        SELECT n.nspname, c.relname, k.conname, k.contype, pg_get_constraintdef(k.oid)
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'
        ORDER BY n.nspname, c.relname, k.conname
    """).fetchall()]
    for schema, name in conn.execute("""
        SELECT schemaname, sequencename FROM pg_sequences
        WHERE schemaname NOT LIKE 'pg_%' ORDER BY schemaname, sequencename
    """).fetchall():
        row = conn.execute(sql.SQL("SELECT last_value, is_called FROM {}").format(sql.Identifier(schema, name))).fetchone()
        result["sequences"][f"{schema}.{name}"] = list(row)
    return result


def backup(pg_bin, options, database, output):
    output = Path(output).resolve()
    manifest_path = output.with_suffix(output.suffix + ".json")
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or manifest_path.exists() or partial.exists():
        raise ValueError("Backup path already exists; choose a new filename.")
    output.parent.mkdir(parents=True, exist_ok=True)
    version = run_program(pg_bin, "pg_dump", ["--version"], options, database)
    try:
        with psycopg.connect(**options, dbname=database) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            server_version = conn.info.server_version
            if server_version // 10000 > int(version.split()[-1].split('.')[0]):
                raise ValueError("pg_dump must be at least as new as the source server major version.")
            expected = fingerprint(conn)
            run_program(pg_bin, "pg_dump", ["--no-password", "--format=custom", "--no-owner", "--no-privileges",
                        "--snapshot=" + snapshot, "--file=" + str(partial)], options, database)
        digest = file_sha256(partial)
        manifest = {"format": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "source": {"host": options["host"], "port": options["port"], "database": database},
                    "server_version": server_version, "pg_dump": version, "archive_sha256": digest,
                    "fingerprint": expected}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        partial.replace(output)
    except BaseException:
        partial.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    print(f"Backup complete: {output}")
    print(f"Verification manifest: {manifest_path}")
    return manifest


def restore_verify(pg_bin, options, archive, keep=False):
    if options["host"] not in {"127.0.0.1", "::1"}:
        raise ValueError("Refusing to restore outside a disposable loopback cluster.")
    archive = Path(archive).resolve()
    manifest = json.loads(archive.with_suffix(archive.suffix + ".json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or file_sha256(archive) != manifest["archive_sha256"]:
        raise ValueError("Backup checksum/manifest verification failed.")
    name = "eee_restore_verify_" + secrets.token_hex(10)
    created, verified = False, False
    with psycopg.connect(**options, dbname="postgres", autocommit=True) as admin:
        # CREATE DATABASE fails safely on collision. Never use --clean, drop an
        # existing name, trust POSTGRES_DB as a target, or reconnect to Aiven.
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
        created = True
        try:
            run_program(pg_bin, "pg_restore", ["--no-password", "--exit-on-error", "--single-transaction",
                        "--no-owner", "--no-privileges", "--dbname=" + name, str(archive)], options, name)
            with psycopg.connect(**options, dbname=name) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                actual = fingerprint(conn)
            if actual != manifest["fingerprint"]:
                raise RuntimeError("Restored tables, rows, constraints or sequences do not match the backup manifest.")
            verified = True
            print(f"Restore verified: {len(actual['tables'])} tables; row hashes, constraints and sequences match.")
            return {"database": name, "verified": True, "tables": len(actual["tables"])}
        finally:
            if created and not (keep and verified):
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
                print("Disposable restore database removed.")
            elif keep and verified:
                print(f"Verified synthetic restore retained: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("backup")
    create.add_argument("--output", type=Path, default=ROOT / "backups" / ("postgres-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".dump"))
    create.add_argument("--local-synthetic", action="store_true", help="Only for a disposable literal loopback source")
    restore = commands.add_parser("restore-verify")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--keep-verified-database", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            options = connection_options(local=args.local_synthetic)
            database = os.environ.get("POSTGRES_DB", "")
            if not database:
                raise ValueError("Set POSTGRES_DB in the current terminal.")
            backup(args.pg_bin, options, database, args.output)
        else:
            options = connection_options("RESTORE_POSTGRES_", local=True)
            restore_verify(args.pg_bin, options, args.archive, args.keep_verified_database)
    except (psycopg.Error, OSError, ValueError, RuntimeError, KeyError) as error:
        if isinstance(error, psycopg.Error):
            message = "Database connection/query failed. Provider error and credentials were suppressed."
        else:
            message = str(error)
        print("Backup verification failed: " + message, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
