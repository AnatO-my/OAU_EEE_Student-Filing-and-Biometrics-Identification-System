"""Create only a new isolated demo database; invoked by prepare-vercel-demo.ps1.

The plan is secret-bearing JSON consumed privately by PowerShell. The create
command reads it from stdin. Neither command migrates or copies existing data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate_bundle(bundle):
    env = bundle["environment"]
    name = env["POSTGRES_DB"]
    if not re.fullmatch(r"eee_demo_[0-9]{8}_[0-9a-f]{8}", name):
        raise ValueError("Invalid isolated database name")
    if env["POSTGRES_USER"] != name + "_app":
        raise ValueError("Invalid dedicated role")
    if env["POSTGRES_SSLMODE"] != "verify-full" or env["DEMO_SYNTHETIC_ONLY"] != "true":
        raise ValueError("Demo isolation and verified TLS are required")
    if env["POSTGRES_DB"] == os.environ.get("POSTGRES_DB"):
        raise ValueError("The existing database cannot be the demo target")
    return env


def plan():
    for key in ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PASSWORD", "POSTGRES_SSLROOTCERT"):
        if not os.environ.get(key):
            raise ValueError("Missing admin connection setting: " + key)
    if not os.environ["POSTGRES_HOST"].endswith(".aivencloud.com"):
        raise ValueError("Expected the configured Aiven service")
    link = json.loads((ROOT / ".vercel/project.json").read_text(encoding="utf-8-sig"))
    if link.get("projectName") != "oau-eee-demo":
        raise ValueError("Expected the linked demo project")
    name = "eee_demo_" + datetime.now(timezone.utc).strftime("%Y%m%d") + "_" + secrets.token_hex(4)
    bundle = {"project_id": link["projectId"], "team_id": link["orgId"], "environment": {
        "DJANGO_SETTINGS_MODULE": "config.vercel_settings",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
        "DJANGO_ALLOWED_HOSTS": "oau-eee-demo.vercel.app",
        "DEMO_PUBLIC_ORIGIN": "https://oau-eee-demo.vercel.app",
        "DEMO_SYNTHETIC_ONLY": "true",
        "POSTGRES_HOST": os.environ["POSTGRES_HOST"],
        "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "POSTGRES_DB": name,
        "POSTGRES_USER": name + "_app",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(36),
        "POSTGRES_SSLMODE": "verify-full",
        "AIVEN_CA_PEM": Path(os.environ["POSTGRES_SSLROOTCERT"]).read_text(encoding="utf-8"),
        "DEMO_EMAIL_ENABLED": "false",
        "RESULT_SHARING_ENABLED": "false",
    }}
    validate_bundle(bundle)
    # Only the PowerShell wrapper captures this output and encrypts it with DPAPI.
    print(json.dumps(bundle))


def create():
    import psycopg
    from psycopg import sql

    env = validate_bundle(json.load(sys.stdin))
    if env["POSTGRES_HOST"] != os.environ["POSTGRES_HOST"]:
        raise ValueError("Service mismatch")
    connection = dict(host=os.environ["POSTGRES_HOST"], port=os.environ["POSTGRES_PORT"],
                      dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
                      password=os.environ["POSTGRES_PASSWORD"], sslmode="verify-full",
                      sslrootcert=os.environ["POSTGRES_SSLROOTCERT"], connect_timeout=15)
    with psycopg.connect(**connection, autocommit=True) as conn:
        if not conn.pgconn.ssl_in_use:
            raise ValueError("Verified TLS is required")
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (env["POSTGRES_DB"],)).fetchone():
            raise ValueError("Refusing an existing database")
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (env["POSTGRES_USER"],)).fetchone():
            raise ValueError("Refusing an existing role")
        role, database = sql.Identifier(env["POSTGRES_USER"]), sql.Identifier(env["POSTGRES_DB"])
        admin = sql.Identifier(conn.execute("SELECT current_user").fetchone()[0])
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 5").format(role, sql.Literal(env["POSTGRES_PASSWORD"])))
        conn.execute(sql.SQL("GRANT {} TO {} WITH SET TRUE, INHERIT FALSE").format(role, admin))
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0").format(database, role))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
        conn.execute(sql.SQL("REVOKE {} FROM {}").format(role, admin))
    connection.update(dbname=env["POSTGRES_DB"], user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"])
    with psycopg.connect(**connection) as conn:
        if conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'").fetchone()[0]:
            raise ValueError("Expected an empty demo database")
        role_flags = conn.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname=current_user").fetchone()
        if any(role_flags):
            raise ValueError("Unexpected elevated role")
    print("Verified dedicated demo role, empty database, and TLS; existing application data was not changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "create"))
    args = parser.parse_args()
    try:
        {"plan": plan, "create": create}[args.command]()
    except Exception as exc:
        # Database provider messages may contain connection data. Show only safe identifiers.
        print("Demo preparation failed: " + type(exc).__name__ + " (SQLSTATE " + str(getattr(exc, "sqlstate", None) or "none") + "). Ask Codex to inspect the failed stage.", file=sys.stderr)
        raise SystemExit(1) from None
