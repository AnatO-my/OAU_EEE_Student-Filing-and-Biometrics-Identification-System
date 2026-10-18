# Attendance backend reconciliation — 18 October 2026

The pending attendance/calendar work was reconciled onto `main` at
`2395e56cb1768fcd069efd3d7dee483e3c03d663` in `feat/attendance-backend`.
The original working checkout and its unrelated pending changes were preserved.

## Included changes

- Attendance course assignments, approved rosters and immutable roster revisions,
  class sessions, idempotent manual events, corrections and student own-history.
- Bounded raw JSONL capture preview/import with immutable evidence, whole-file
  digest confirmation, append/retry rules and durable receipts. Imports remain
  pending identity/timing review and do not create attendance marks.
- HOD current-academic-session selection, audit history and guarded updates.
  `CURRENT_ACADEMIC_SESSION` remains a bootstrap fallback until a database
  selection is made. The current-session API returns ID/name/source from one
  database read, avoiding inconsistent fields during concurrent selection.
- Database-selected adviser scope across account identity, student reads/writes,
  results, guardians, CSV export, messaging **and the document-upload feature
  already on main**. New integration tests cover these cross-module boundaries.
- Both document and attendance URL configurations/settings are retained. Package
  discovery includes both apps; CI and the PostgreSQL runner test both.
- The downloader's three Python helper modules are included solely as the source
  contract used by the synthetic interoperability test. No device commands,
  physical scans, firmware changes or private capture/template files were used.

The import deliberately excludes unrelated SMTP/email-worker changes, data
conversion work, student datasets, generated reports and other hardware work.

## Schema and access

The existing migrations are preserved. This adds academic migration `0006` for
current-session selection, and attendance migrations `0001`–`0003` for rosters,
classes, manual/correction history, pending captures and receipts. The migration
graph includes the document app unchanged. Existing source models and IDs are
not replaced by models from the external frontend repository.

HOD selects the current session through Django admin or
`GET/PUT /api/academic-sessions/current/`. PUT supplies `academic_session` and
the reviewed `expected_session_id`; stale choices are rejected. Ordinary course
staff need the action-specific attendance permission and an active course
assignment in that selected session. Raw-capture import additionally requires
`attendance.import_pending_captures`. HOD retains historical review access.

Changing the current session does not edit adviser/course assignments, roster
snapshots or past records. Document uploads and CSV export now use the same
selected adviser scope as student reads, instead of a separate environment scope.

Migrations were exercised only in isolated test databases. Applying them to an
existing development/shared database still depends on its separate schema/data
reconciliation; no such database was migrated during this work.

## Validation

- Django system checks and missing-migration checks pass.
- The calendar/document integration suite passes: 23 tests on isolated SQLite.
- A local wheel build succeeds and contains attendance, its capture migrations,
  the calendar resolver and the existing document app.
- The complete backend suite passes: **360 tests on isolated PostgreSQL 16.15,
  with no skips**, including 14 contention cases, seven real HTTP/restart cases
  and the document regression suite. System and migration-drift checks pass.
  The runner stopped and removed its temporary cluster after success.

To reproduce the full backend checks from a configured checkout:

```powershell
python tools/run_attendance_postgres_tests.py --pg-bin 'PATH_TO_TRUSTED_PG_BIN'
```

This creates a new loopback-only PostgreSQL cluster with generated test
credentials, runs checks and all five application test suites, stops its server,
and removes only its verified temporary cluster after success. It never selects
the existing application database. The runner retains a stopped failed cluster
for diagnosis.

See [attendance-api.md](attendance-api.md),
[attendance-pending-batches.md](attendance-pending-batches.md) and the historical
[16 October validation checkpoint](attendance-validation.md) for the contracts
and limitations. Matching, device authentication, trusted capture clocks,
reconciliation of pending captures into marks and attendance warning metrics
remain separate unfinished features.
