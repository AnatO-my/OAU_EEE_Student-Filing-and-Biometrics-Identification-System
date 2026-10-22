"""Run checks against a disposable loopback PostgreSQL cluster, never an existing DB.

Usage: .venv/Scripts/python.exe tools/run_attendance_postgres_tests.py --pg-bin PATH
The runtime must already be obtained from a trusted publisher; this does not install it.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile

import psycopg


WORKSPACE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--keep-cluster", action="store_true", help="Retain stopped synthetic cluster for diagnosis")
    parser.add_argument("--backup-drill", action="store_true", help="Also migrate the synthetic source and prove backup/restore")
    parser.add_argument("--connection-file", type=Path, help="Explicitly retain synthetic cluster credentials in ignored private-data/")
    parser.add_argument("--skip-tests", action="store_true", help="Prepare a fresh synthetic cluster and optional backup drill only")
    parser.add_argument("--restore-archive", type=Path, help="Verify an existing archive in this fresh disposable cluster")
    parser.add_argument("--backup-client-bin", type=Path, help="Optional separate pg_dump/pg_restore client directory")
    parser.add_argument("labels", nargs="*", default=["students", "accounts", "academics", "attendance", "record_imports"])
    args = parser.parse_args()
    suffix = ".exe" if os.name == "nt" else ""
    pg_bin = args.pg_bin.resolve()
    connection_file = args.connection_file.resolve() if args.connection_file else None
    if connection_file and (not connection_file.is_relative_to((WORKSPACE / "private-data").resolve()) or connection_file.exists()):
        parser.error("connection-file must be a new file inside ignored private-data/")
    if connection_file and not args.keep_cluster:
        parser.error("connection-file requires --keep-cluster")
    programs = {name: pg_bin / (name + suffix) for name in ("initdb", "pg_ctl", "postgres")}
    if not all(path.is_file() for path in programs.values()):
        parser.error("pg-bin must contain initdb, pg_ctl and postgres")
    test_root = WORKSPACE / "tmp"
    test_root.mkdir(exist_ok=True)
    cluster_root = Path(tempfile.mkdtemp(prefix="attendance-postgres-", dir=test_root)).resolve()
    data = cluster_root / "data"
    password_file = cluster_root / "bootstrap-password.txt"
    password = secrets.token_urlsafe(32)
    password_file.write_text(password + "\n", encoding="ascii")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {**os.environ, "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": str(port),
           "POSTGRES_DB": "attendance_validation", "POSTGRES_USER": "attendance_test",
           "POSTGRES_PASSWORD": password, "DJANGO_SETTINGS_MODULE": "config.ci_settings"}
    # A user's Aiven terminal may export verify-full or hostaddr. A disposable
    # loopback test must never inherit that transport or a connection service.
    env = {key: value for key, value in env.items() if not key.startswith("PG")}
    env.update(PGSSLMODE="disable", PGGSSENCMODE="disable", PGPASSFILE=os.devnull)
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    started, success = False, False
    try:
        with (cluster_root / "initdb.log").open("wb") as log:
            subprocess.run([str(programs["initdb"]), "-D", str(data), "-U", "attendance_test",
                            "--pwfile", str(password_file), "-A", "scram-sha-256", "-E", "UTF8", "--no-locale"],
                           check=True, stdout=log, stderr=subprocess.STDOUT, timeout=60, **flags)
        password_file.unlink()
        subprocess.run([str(programs["pg_ctl"]), "-D", str(data), "-l", str(cluster_root / "postgres.log"),
                        "-o", f"-h 127.0.0.1 -p {port}", "-w", "-t", "30", "start"], check=True, timeout=40,
                       stdout=sys.stdout, stderr=sys.stderr, **flags)
        started = True
        with psycopg.connect(host="127.0.0.1", port=port, user="attendance_test", password=password,
                             dbname="postgres", sslmode="disable", autocommit=True) as conn:
            conn.execute('CREATE DATABASE attendance_validation')
        subprocess.run([str(programs["postgres"]), "--version"], check=True, stdout=sys.stdout, stderr=sys.stderr, **flags)
        print(f"Synthetic test cluster: 127.0.0.1:{port}. No Windows service installed.", flush=True)
        if connection_file:
            connection_file.parent.mkdir(parents=True, exist_ok=True)
            connection_file.write_text(json.dumps({"synthetic_only": True, "data_directory": str(data),
                "pg_bin": str(pg_bin), "host": "127.0.0.1", "port": port,
                "database": "attendance_validation", "user": "attendance_test", "password": password,
                "sslmode": "disable"}, indent=2) + "\n", encoding="utf-8")
            print(f"Synthetic connection file retained privately: {connection_file}", flush=True)
        commands = [
            ["check"], ["makemigrations", "--check", "--dry-run"],
            ["test", *args.labels, "--noinput"],
        ]
        for command in ([] if args.skip_tests else commands):
            subprocess.run([sys.executable, str(WORKSPACE / "manage.py"), *command, "--settings=config.ci_settings"],
                           cwd=WORKSPACE, env=env, check=True, stdout=sys.stdout, stderr=sys.stderr, **flags)
        if args.backup_drill:
            subprocess.run([sys.executable, str(WORKSPACE / "manage.py"), "migrate", "--noinput", "--verbosity=0",
                            "--settings=config.ci_settings"], cwd=WORKSPACE, env=env, check=True, **flags)
            from postgres_backup_drill import drill
            drill(args.backup_client_bin or pg_bin, {"host": "127.0.0.1", "port": port, "user": "attendance_test", "password": password,
                           "sslmode": "disable", "connect_timeout": 10}, "attendance_validation", cluster_root)
        if args.restore_archive:
            from postgres_backup import restore_verify
            restore_verify(args.backup_client_bin or pg_bin,
                           {"host": "127.0.0.1", "port": port, "user": "attendance_test", "password": password,
                            "sslmode": "disable", "connect_timeout": 10}, args.restore_archive)
        success = True
    finally:
        if password_file.exists():
            password_file.unlink()
        # Also handle a start command that timed out after spawning postgres.
        stopped = True
        if started or (data / "postmaster.pid").exists():
            stop = subprocess.run([str(programs["pg_ctl"]), "-D", str(data), "-m", "fast", "-w", "-t", "30", "stop"],
                                  timeout=40, stdout=sys.stdout, stderr=sys.stderr, **flags)
            stopped = stop.returncode == 0
        if success and stopped and not args.keep_cluster:
            # Verify the absolute target before recursively removing only our new cluster.
            if cluster_root.parent != test_root.resolve() or not cluster_root.name.startswith("attendance-postgres-"):
                raise RuntimeError("Refusing cleanup outside the synthetic test directory.")
            shutil.rmtree(cluster_root)
        else:
            print(f"Synthetic cluster files/logs retained: {cluster_root}", flush=True)
        if not stopped:
            raise RuntimeError("Test PostgreSQL did not stop; cluster retained for diagnosis.")


if __name__ == "__main__":
    main()
