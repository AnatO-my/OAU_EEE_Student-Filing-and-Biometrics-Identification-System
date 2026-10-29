"""Supervise the laptop's loopback-only Django, Vite and optional email worker."""

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
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
PORTAL = ROOT / "frontend" / "portal"
BACKEND_PORT = 8000
FRONTEND_PORT = 5175
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def local_environment(backend_port=BACKEND_PORT, frontend_port=FRONTEND_PORT):
    environment = os.environ.copy()
    if environment.get("DJANGO_SETTINGS_MODULE") != "config.postgres_settings":
        raise RuntimeError("Configure this terminal with private-data/aiven/configure.ps1 before starting the application.")
    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    if any(not environment.get(name) for name in required):
        raise RuntimeError("Database connection settings are incomplete. Run the Aiven terminal configuration again.")
    if environment.get("POSTGRES_SSLMODE") != "verify-full":
        raise RuntimeError("The laptop Aiven profile must use POSTGRES_SSLMODE=verify-full.")
    certificate = environment.get("POSTGRES_SSLROOTCERT", "")
    if not certificate or not Path(certificate).is_file():
        raise RuntimeError("The Aiven CA certificate is missing. Check POSTGRES_SSLROOTCERT.")
    # Local HTTP and same-origin Vite proxy. Never use this profile for a public
    # interface: all listener addresses below are explicitly loopback-only.
    environment.update({
        "DJANGO_DEBUG": "true",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "DJANGO_SECURE_TRANSPORT": "false",
        "PYTHONUNBUFFERED": "1",
        "VITE_API_PROXY_TARGET": f"http://127.0.0.1:{backend_port}",
        "STUDENT_ACCOUNT_FRONTEND_ORIGIN": f"http://127.0.0.1:{frontend_port}",
    })
    environment.setdefault("TEACHING_PORTAL_URL", f"http://127.0.0.1:{frontend_port}/portal")
    # Student-access emails use this launcher's actual frontend port. Ordinary
    # recovery stays disabled with a console backend so reset links cannot be
    # printed to terminal output instead of being sent privately.
    if environment.get("DJANGO_EMAIL_BACKEND") in {
        "academics.email_backend.EmailBackend", "django.core.mail.backends.smtp.EmailBackend",
    } and all(environment.get(name, "").strip() for name in (
        "DJANGO_EMAIL_HOST", "DJANGO_EMAIL_HOST_USER", "DJANGO_EMAIL_HOST_PASSWORD",
    )):
        if not environment.get("PASSWORD_RESET_FRONTEND_URL", "").strip():
            environment["PASSWORD_RESET_FRONTEND_URL"] = f"http://127.0.0.1:{frontend_port}/reset-password"
    trusted = {value.strip() for value in environment.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if value.strip()}
    trusted.add(f"http://127.0.0.1:{frontend_port}")
    environment["DJANGO_CSRF_TRUSTED_ORIGINS"] = ",".join(sorted(trusted))
    environment.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(64))
    return environment


def checked_command(arguments, environment, *, label="Startup check", hint="Resolve this check before starting local services."):
    print(f"Checking: {label}", flush=True)
    # CREATE_NO_WINDOW can detach a child's console handles on Windows. Capture
    # explicitly and forward through this supervisor so errors remain visible.
    command_environment = {**environment, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(arguments, cwd=ROOT, env=command_environment,
        creationflags=NO_WINDOW, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for output in (result.stdout, result.stderr):
        # Never echo configured credentials even if a dependency includes one in
        # a traceback. The connection command already uses fixed diagnostics.
        for name, value in environment.items():
            if value and any(part in name.upper() for part in ("PASSWORD", "TOKEN", "SECRET")):
                output = output.replace(value, "[redacted]")
        if output.strip():
            print(output.rstrip(), flush=True)
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit {result.returncode}). {hint}")
    print(f"Passed: {label}", flush=True)


def check_port(port):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(f"Port {port} is already in use. Stop the existing server in its terminal with Ctrl+C, then retry.") from None


def check_worker(environment):
    if environment.get("RESULT_SHARING_ENABLED", "false").lower() != "true":
        raise RuntimeError("The email worker requires RESULT_SHARING_ENABLED=true and a configured email provider. Omit -EmailWorker to run the portal alone.")
    if not environment.get("DJANGO_EMAIL_HOST") or not environment.get("DJANGO_EMAIL_HOST_USER") or not environment.get("DJANGO_EMAIL_HOST_PASSWORD"):
        raise RuntimeError("Configure Gmail privately in this terminal before enabling the email worker. See docs/guardian-email-setup.md.")
    backend = environment.get("DJANGO_EMAIL_BACKEND", "")
    if backend not in {"academics.email_backend.EmailBackend", "django.core.mail.backends.smtp.EmailBackend"}:
        raise RuntimeError("Select the configured SMTP email backend before enabling the email worker.")


def check_teaching_worker(environment):
    backend = environment.get("DJANGO_EMAIL_BACKEND", "")
    if backend not in {"academics.email_backend.EmailBackend", "django.core.mail.backends.smtp.EmailBackend"} or not all(
        environment.get(name, "").strip() for name in ("DJANGO_EMAIL_HOST", "DJANGO_EMAIL_HOST_USER", "DJANGO_EMAIL_HOST_PASSWORD")
    ):
        raise RuntimeError("Configure the private SMTP provider before using -TeachingNotifications. Normal startup does not send announcements.")
    origin = urlparse(environment.get("TEACHING_PORTAL_URL", ""))
    if origin.scheme not in {"http", "https"} or not origin.netloc or origin.username or origin.password or origin.query or origin.fragment:
        raise RuntimeError("Set TEACHING_PORTAL_URL to the website's absolute portal URL before starting announcement notifications.")


def stop_children(children, stop_file):
    # These are exact Popen handles created here; never stop a process discovered
    # by port or name, and never terminate an unrelated server or worker.
    if any(name in {"email worker", "teaching notification worker"} and process.poll() is None for name, process in children):
        stop_file.touch()
        for name, process in children:
            if name in {"email worker", "teaching notification worker"}:
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    print("The email worker did not stop within 30 seconds. Stopping it; review any processing delivery before retrying.", flush=True)
    for name, process in reversed(children):
        if process.poll() is None:
            process.terminate()
    for name, process in reversed(children):
        try:
            process.wait(timeout=30 if name in {"email worker", "teaching notification worker"} else 10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_ready(children, url, *, database=False):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        for name, process in children:
            if process.poll() is not None:
                raise RuntimeError(f"The {name} process exited during startup. Review its output above.")
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    if not database or json.load(response) == {"status": "ok"}:
                        return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.3)
    raise RuntimeError("Local services did not become ready within 60 seconds. Review their output above.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email-worker", action="store_true", help="Process queued email reports using this terminal's configured provider.")
    parser.add_argument("--teaching-notifications", action="store_true", help="Explicitly process queued announcement emails with the configured SMTP provider.")
    parser.add_argument("--check-only", action="store_true", help="Perform read-only prerequisites without starting any server or worker.")
    parser.add_argument("--backend-port", type=int, default=BACKEND_PORT)
    parser.add_argument("--frontend-port", type=int, default=FRONTEND_PORT)
    options = parser.parse_args()
    if not (1 <= options.backend_port <= 65535 and 1 <= options.frontend_port <= 65535) or options.backend_port == options.frontend_port:
        parser.error("Choose two different ports between 1 and 65535.")
    environment = local_environment(options.backend_port, options.frontend_port)
    node = shutil.which("node")
    vite = PORTAL / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.is_file():
        raise RuntimeError("Install Node.js and run npm ci in frontend/portal first. See docs/local-laptop.md.")
    if options.email_worker:
        check_worker(environment)
    if options.teaching_notifications:
        check_teaching_worker(environment)
    print("Checking the configured PostgreSQL connection and pending migrations...", flush=True)
    checked_command([sys.executable, "manage.py", "check_database_connection"], environment,
        label="PostgreSQL connection", hint="Run manage.py check_database_connection in this configured terminal and resolve its diagnostic.")
    checked_command([sys.executable, "manage.py", "migrate", "--check"], environment,
        label="Migration readiness", hint="Run .\\.venv\\Scripts\\python.exe manage.py migrate --plan. If migrations are pending, stop all local servers/workers and run .\\scripts\\update-local.ps1 for the backed-up update.")
    if options.check_only:
        print("Local prerequisites passed. No server, worker, migration or import was started.", flush=True)
        return 0
    check_port(options.backend_port)
    check_port(options.frontend_port)
    children = []
    # Only a stop marker is written; passwords remain in the inherited process
    # environment. The temporary directory is private working data, not a log.
    (ROOT / "tmp").mkdir(exist_ok=True)
    session_directory = Path(tempfile.mkdtemp(prefix="local-session-", dir=ROOT / "tmp"))
    stop_file = session_directory / "stop-worker"
    try:
        commands = [
            ("backend", [sys.executable, "manage.py", "runserver", f"127.0.0.1:{options.backend_port}", "--noreload"]),
            ("frontend", [node, str(vite), "--host", "127.0.0.1", "--port", str(options.frontend_port), "--strictPort"]),
        ]
        if options.email_worker:
            commands.append(("email worker", [sys.executable, "manage.py", "process_result_shares", "--channel", "email", "--watch", "--interval", "5", "--limit", "25", "--stop-file", str(stop_file)]))
        if options.teaching_notifications:
            commands.append(("teaching notification worker", [sys.executable, "manage.py", "send_teaching_notifications", "--watch", "--interval", "5", "--limit", "25", "--stop-file", str(stop_file)]))
        for name, command in commands:
            children.append((name, subprocess.Popen(command, cwd=PORTAL if name == "frontend" else ROOT, env=environment,
                creationflags=NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0))))
        wait_ready(children, f"http://127.0.0.1:{options.backend_port}/health/ready/", database=True)
        wait_ready(children, f"http://127.0.0.1:{options.frontend_port}/")
        print(f"\nPortal ready: http://127.0.0.1:{options.frontend_port}/", flush=True)
        print(f"Administrator: http://127.0.0.1:{options.backend_port}/admin/", flush=True)
        print("Keep this terminal open. Press Ctrl+C to stop the services started here.", flush=True)
        while True:
            for name, process in children:
                if process.poll() is not None:
                    raise RuntimeError(f"The {name} stopped; shutting down this local application session.")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping local services...", flush=True)
    finally:
        stop_children(children, stop_file)
        stop_file.unlink(missing_ok=True)
        session_directory.rmdir()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(f"Local startup: {error}", file=sys.stderr)
        sys.exit(1)
