"""Stage a later operator rehearsal in a fresh, guarded scratch environment.

No workflow runs without an explicit subcommand. --help and self-check do not
initialize Django, create a database, send email, or touch hardware.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone as utc_timezone
import getpass
import json
import os
import re
import secrets
from pathlib import Path
import sys
import uuid
from urllib.parse import urlsplit

REPOSITORY = Path(__file__).resolve().parents[1]
PURPOSE = "EEE_ISOLATED_EVALUATION"
SETTINGS = "config.evaluation_settings"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def scratch_root(value):
    root = Path(value).resolve(strict=True)
    marker = json.loads((root / "evaluation-scratch.json").read_text(encoding="utf-8"))
    if marker.get("purpose") != PURPOSE or marker.get("root") != str(root) or marker.get("schema_version") != 1:
        raise RuntimeError("Refusing an unrecognized evaluation directory.")
    for name in ("scratch.sqlite3", "private-media", "fixtures", "run-manifest.json", "session-secret.txt"):
        if (root / name).resolve().parent != root:
            raise RuntimeError("Scratch paths must remain inside the initialized run.")
    return root, marker


def frontend_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or "*" in value or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Use one exact HTTPS frontend origin, without wildcards, credentials, path, query or fragment.")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", parsed.hostname):
        raise ValueError("Use an exact DNS hostname for the forwarded origin.")
    parsed.port  # Reject invalid port syntax/range.
    return "https://" + parsed.hostname.lower() + (":" + str(parsed.port) if parsed.port else "")


def initialize(args):
    root = Path(args.root).resolve()
    if root == REPOSITORY or root in REPOSITORY.parents:
        raise RuntimeError("The repository or an ancestor cannot be a scratch root.")
    root.mkdir(parents=True, exist_ok=False)  # Never reuse or overwrite any existing directory.
    run_id = str(uuid.uuid4())
    write_json(root / "evaluation-scratch.json", {"schema_version": 1, "purpose": PURPOSE,
        "run_id": run_id, "root": str(root), "created_at": datetime.now(utc_timezone.utc).isoformat()})
    (root / "session-secret.txt").write_text(secrets.token_urlsafe(50), encoding="utf-8")
    (root / "fixtures").mkdir()
    (root / "private-media").mkdir()
    (root / "evidence").mkdir()
    print(f"Initialized scratch marker/private session key only: {root}")
    print("No database, migrations, accounts, mail, scanner or workflows have been run.")


def activate(root):
    existing = os.environ.get("DJANGO_SETTINGS_MODULE")
    if existing and existing != SETTINGS:
        raise RuntimeError("Unset DJANGO_SETTINGS_MODULE; this launcher refuses normal/production settings.")
    os.environ["EEE_EVALUATION_ROOT"] = str(root)
    os.environ["DJANGO_SETTINGS_MODULE"] = SETTINGS
    sys.path.insert(0, str(REPOSITORY / "app"))
    import django
    django.setup()
    from django.conf import settings
    if (settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"
            or Path(settings.DATABASES["default"]["NAME"]).resolve() != root / "scratch.sqlite3"
            or Path(settings.PRIVATE_MEDIA_ROOT).resolve() != root / "private-media"
            or settings.EMAIL_BACKEND != "django.core.mail.backends.locmem.EmailBackend"):
        raise RuntimeError("Refusing non-scratch persistence or a non-locmem mail backend.")


def prepare(args):
    root, marker = scratch_root(args.root)
    if (root / "scratch.sqlite3").exists() or (root / "run-manifest.json").exists():
        raise RuntimeError("Prepare only a new scratch run. Existing databases are never migrated or reseeded; initialize another run directory.")
    password = getpass.getpass("Choose a strong SYNTHETIC rehearsal password (not a real account password): ")
    if password != getpass.getpass("Confirm synthetic password: "):
        raise RuntimeError("Passwords did not match; no database was created.")
    activate(root)
    from django.contrib.auth.password_validation import validate_password
    validate_password(password)
    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)  # Only the new guarded scratch.sqlite3 above.
    manifest = seed(root, marker, password)
    write_json(root / "run-manifest.json", manifest)
    print(f"Prepared isolated synthetic fixtures: {root / 'run-manifest.json'}")
    print("Password was not logged or stored in the manifest. No current import, mail delivery, device or operator case was executed.")


def seed(root, marker, password):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission
    from django.db import transaction
    from django.utils import timezone
    from accounts.administration import MANAGED_PERMISSIONS
    from accounts.models import AdviserAssignment
    from students.services import create_student
    from academics.models import AcademicSession, Course, CourseOffering, CurrentAcademicSession
    from academics.current_session import select_current_session
    from academics.grading import INITIAL_BANDS
    from academics.services import create_grading_scale, publish_grading_scale, create_result, verify_result
    from attendance.services import assign_staff, confirm_roster, open_session
    from attendance.test_pending_batches import header, event, pack
    handles, students, offerings, meetings = {}, {}, {"prior": {}, "current": {}, "teaching": {}}, {}
    with transaction.atomic():
        User = get_user_model()
        role_names = ["EVAL-HOD", "EVAL-HOD-SUCCESSOR", "EVAL-ADVISER", "EVAL-LECTURER", "EVAL-UNASSIGNED", "EVAL-STUDENT-A", "EVAL-STUDENT-B", "EVAL-SETUP"]
        accounts = {}
        for handle in role_names:
            username = {"EVAL-STUDENT-A": "EVAL/001", "EVAL-STUDENT-B": "EVAL/002", "EVAL-SETUP": "EVAL/003"}.get(handle, handle)
            account = User.objects.create_user(username=username, password=password,
                email=handle.lower() + "@example.invalid", is_staff="STUDENT" not in handle and handle != "EVAL-SETUP",
                is_superuser=handle == "EVAL-HOD", must_change_password=handle == "EVAL-SETUP")
            if account.is_staff and not account.is_superuser:
                codes = Permission.objects.select_related("content_type")
                account.user_permissions.add(*[permission for permission in codes
                    if f"{permission.content_type.app_label}.{permission.codename}" in MANAGED_PERMISSIONS])
            accounts[handle] = account
            handles[handle] = {"username": username, "user_id": account.pk, "email": account.email,
                "must_change_password": account.must_change_password}
        hod = accounts["EVAL-HOD"]
        prior_year = AcademicSession.objects.create(name="2025/2026")
        year = AcademicSession.objects.create(name="2026/2027")
        select_current_session(user=hod, academic_session=year, expected_session_id=CurrentAcademicSession.objects.get(pk=1).academic_session_id)
        scale = create_grading_scale(user=hod, validated_data={"name": "SYNTHETIC EVALUATION five-point scale", "bands": INITIAL_BANDS})
        scale = publish_grading_scale(user=hod, scale=scale)
        for label, identifier, handle in (("A", "EVAL/001", "EVAL-STUDENT-A"), ("B", "EVAL/002", "EVAL-STUDENT-B"), ("SETUP", "EVAL/003", "EVAL-SETUP")):
            student = create_student(user=hod, validated_data={"identifier_type": "matriculation", "identifier_value": identifier,
                "full_name": "Evaluation Student " + label, "phone_number": "+2340000000000", "admission_year": 2024,
                "mode_of_admission": "utme", "current_level": 300, "user": accounts[handle]})
            students[label] = {"student_id": str(student.pk), "identifier": identifier, "user_id": accounts[handle].pk, "name": student.full_name}
        from students.models import Student
        pair = list(Student.objects.filter(pk__in=[students["A"]["student_id"], students["B"]["student_id"]]))
        AdviserAssignment.objects.create(staff=accounts["EVAL-ADVISER"], academic_session=year.name, level=300)
        prior_spec = [("EVAL101",3,72),("EVAL103",2,65),("EVAL105",3,35)]
        current_spec = [("EVAL201",3),("EVAL203",3),("EVAL205",2),("EVAL207",2),("EVAL209",1),("EVAL105",3)]
        for code, units, score in prior_spec:
            course, _ = Course.objects.get_or_create(code=code, defaults={"title": "Synthetic evaluation " + code})
            offering = CourseOffering.objects.create(course=course, academic_session=prior_year, semester="harmattan", level=300, credit_units=units, grading_scale=scale)
            offerings["prior"][code] = {"offering_id": offering.pk, "units": units}
            for student in pair:
                result = create_result(user=hod, student=student, offering=offering, score=Decimal(score))
                verify_result(user=hod, result=result, expected_score=Decimal(score))
        for code, units in current_spec + [("EEE901",3),("EEE902",3)]:
            course, _ = Course.objects.get_or_create(code=code, defaults={"title": "Synthetic evaluation " + code})
            offering = CourseOffering.objects.create(course=course, academic_session=year, semester="harmattan", level=300, credit_units=units, grading_scale=scale)
            target = "teaching" if code.startswith("EEE") else "current"
            offerings[target][code] = {"offering_id": offering.pk, "units": units}
            for handle in ("EVAL-ADVISER", "EVAL-LECTURER"):
                assign_staff(user=hod, offering=offering, staff=accounts[handle], is_active=True)
            confirm_roster(user=hod, offering=offering, student_ids=[student.pk for student in pair], expected_revision=0)
            if target == "teaching":
                now = timezone.now()
                meeting = open_session(user=accounts["EVAL-LECTURER"], offering=offering,
                    title="SYNTHETIC rehearsal " + code, starts_at=now-timedelta(minutes=10), ends_at=now+timedelta(hours=12))
                meetings["IMPORT" if code == "EEE901" else "WRONG_TARGET"] = {"session_id": str(meeting.pk), "offering_id": offering.pk,
                    "title": meeting.title, "recording_window_ends_at": meeting.ends_at.isoformat()}
    fixture_dir = root / "fixtures"
    metadata = header(meetings["IMPORT"]["session_id"])
    capture = event(boot_id=uuid.uuid4(), uptime=1000, probe=b"SYNTHETIC-ONLY-NOT-A-FINGERPRINT")
    files = {}
    versions = {
        "pending-valid.jsonl": pack(metadata, [capture]),
        "pending-valid-replay.jsonl": pack(metadata, [capture]),
        "pending-append.jsonl": pack(metadata, [capture, event(boot_id=uuid.UUID(capture["boot_uuid"]), uptime=2000, probe=b"SYNTHETIC-ONLY-SECOND-CAPTURE")]),
        "pending-conflict.jsonl": pack(metadata, [{**capture, "uptime_ms": 9999}]),  # Wire JSON integer; storage text is separate.
    }
    for name, payload in versions.items():
        (fixture_dir / name).write_bytes(payload)
        files[name] = str(fixture_dir / name)
    for version in (1,2):
        name = f"material-v{version}.txt"
        (fixture_dir / name).write_text(f"SYNTHETIC TEACHING MATERIAL VERSION {version}\nNot a real student document or teaching resource.\n", encoding="utf-8")
        files[name] = str(fixture_dir / name)
    return {"schema_version": 1, "purpose": PURPOSE, "run_id": marker["run_id"], "root": str(root),
        "settings": SETTINGS, "database": str(root / "scratch.sqlite3"), "private_media": str(root / "private-media"),
        "email_backend": "django.core.mail.backends.locmem.EmailBackend", "backend_url": "http://127.0.0.1:8876",
        "portal_url": "http://127.0.0.1:5175/portal", "role_handles": handles, "students": students,
        "sessions": {"prior": prior_year.name, "current": year.name}, "grading_scale_id": scale.pk,
        "offerings": offerings, "meetings": meetings, "fixtures": files,
        "state": "PREPARED_NOT_EVALUATED", "synthetic_only": True,
        "grading_assumption": "Synthetic five-point bands; all verified attempts counted. Not an institutional repeat-course policy."}


def serve(args):
    root, _ = scratch_root(args.root)
    if not (root / "run-manifest.json").is_file():
        raise RuntimeError("Prepare this scratch run before starting its server.")
    manifest = json.loads((root / "run-manifest.json").read_text(encoding="utf-8"))
    os.environ.pop("EEE_EVALUATION_FRONTEND_ORIGIN", None)
    if args.frontend_origin:
        manifest["frontend_origin"] = frontend_origin(args.frontend_origin)
        os.environ["EEE_EVALUATION_FRONTEND_ORIGIN"] = manifest["frontend_origin"]
    else:
        manifest.pop("frontend_origin", None)
    write_json(root / "run-manifest.json", manifest)
    activate(root)
    from django.core.management import call_command
    call_command("runserver", "127.0.0.1:8876", use_reloader=False)


def capture_notifications(args):
    from time import perf_counter_ns
    root, _ = scratch_root(args.root)
    manifest = json.loads((root / "run-manifest.json").read_text(encoding="utf-8"))
    os.environ.pop("EEE_EVALUATION_FRONTEND_ORIGIN", None)
    if manifest.get("frontend_origin"):
        os.environ["EEE_EVALUATION_FRONTEND_ORIGIN"] = frontend_origin(manifest["frontend_origin"])
    activate(root)
    from django.core import mail
    from teaching.models import Notification
    from teaching.services import send_notification
    pending = list(Notification.objects.filter(state="pending").order_by("pk")[:100])
    if any(not row.destination.lower().endswith("@example.invalid") for row in pending):
        raise RuntimeError("Only synthetic example.invalid notification destinations are accepted.")
    results = []
    for item in pending:
        start = perf_counter_ns()
        state = send_notification(item.pk)
        results.append({"notification_id": item.pk, "state": state, "elapsed_ms": (perf_counter_ns()-start)/1_000_000})
    preview = {"run_id": manifest["run_id"], "transport": "locmem only; NOT SMTP delivery or recipient reading",
        "results": results, "messages": [{"subject": item.subject, "to": item.to, "body": item.body}
        for item in getattr(mail, "outbox", [])]}
    filename = "teaching-notifications-" + datetime.now(utc_timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json"
    target = root / "evidence" / filename
    write_json(target, preview)
    print(f"Synthetic locmem preview captured: {target}")
    print("No real email was sent. Website receipts are unchanged until deliberate recipient opening.")


def self_check(args):
    import ast
    ast.parse(Path(__file__).read_text(encoding="utf-8"))
    ast.parse((REPOSITORY / "app/config/evaluation_settings.py").read_text(encoding="utf-8"))
    assert frontend_origin("https://example.invalid") == "https://example.invalid"
    for candidate in ("https://*.example.invalid", "https://example.invalid/path", "https://u:p@example.invalid", "https://example.invalid?token=x", "http://example.invalid", "https://example .invalid"):
        try:
            frontend_origin(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe frontend origin was accepted")
    # Load only the stdlib parser and the three pure fixture helper function
    # definitions. Do not import the Django test module or initialise Django.
    import base64
    import hashlib
    import importlib.util
    parser_path = REPOSITORY / "app/attendance/pending_format.py"
    specification = importlib.util.spec_from_file_location("_eval_capture_format", parser_path)
    parser_module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = parser_module
    specification.loader.exec_module(parser_module)
    fixture_tree = ast.parse((REPOSITORY / "app/attendance/test_pending_batches.py").read_text(encoding="utf-8"))
    functions = [node for node in fixture_tree.body if isinstance(node, ast.FunctionDef) and node.name in {"header", "event", "pack"}]
    if len(functions) != 3:
        raise AssertionError("The existing pure synthetic fixture helpers changed; review the staging script.")
    helper_scope = {"base64": base64, "hashlib": hashlib, "json": json, "uuid": uuid,
                    "PROBE_FORMAT": parser_module.PROBE_FORMAT}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<pure synthetic fixture helpers>", "exec"), helper_scope)
    metadata = helper_scope["header"](uuid.uuid4())
    first = helper_scope["event"](boot_id=uuid.uuid4(), uptime=1000, probe=b"SYNTHETIC-ONLY-NOT-A-FINGERPRINT")
    second = helper_scope["event"](boot_id=uuid.UUID(first["boot_uuid"]), uptime=2000, probe=b"SYNTHETIC-ONLY-SECOND-CAPTURE")
    baseline = parser_module.parse_capture_file(helper_scope["pack"](metadata, [first]))
    appended = parser_module.parse_capture_file(helper_scope["pack"](metadata, [first, second]))
    conflict = parser_module.parse_capture_file(helper_scope["pack"](metadata, [{**first, "uptime_ms": 9999}]))
    assert len(baseline.events) == 1 and len(appended.events) == 2
    assert all(type(row.uptime_ms) is int for fixture in (baseline, appended, conflict) for row in fixture.events)
    assert baseline.events[0].event_id == conflict.events[0].event_id
    assert baseline.events[0].uptime_ms != conflict.events[0].uptime_ms
    assert baseline.metadata == conflict.metadata == appended.metadata
    sys.modules.pop(specification.name, None)
    print("Harness syntax/origin guards and three in-memory synthetic JSONL variants validated.")
    print("No Django setup, database, migration, seed, importer, mail, account, hardware or operator workflow was run. HTTP 409 remains NOT_RUN.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("init", initialize), ("prepare", prepare), ("serve", serve), ("capture-notifications", capture_notifications)):
        command = commands.add_parser(name)
        command.add_argument("--root", required=True, help="Fresh separate scratch run directory")
        if name == "serve":
            command.add_argument("--frontend-origin", help="Optional exact private HTTPS forwarding origin; no wildcard")
        command.set_defaults(function=function)
    commands.add_parser("self-check").set_defaults(function=self_check)
    args = parser.parse_args()
    try:
        args.function(args)
    except Exception as exc:
        parser.exit(1, f"Refused or failed safely: {exc}\n")

if __name__ == "__main__":
    main()
