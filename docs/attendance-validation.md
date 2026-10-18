# Attendance import validation - 16 October 2026

For the reconciliation with the document app and current `main`, see the
[18 October reconciliation](attendance-reconciliation-2026-10-18.md). This file
retains the earlier checkpoint and its historical test count.

This checkpoint adds PostgreSQL contention tests and loopback HTTP integration
tests for pending capture imports. All fixtures are synthetic. The scanner,
gallery, saved probes, recovery backup and shared/development databases are
outside these tests.

## Verified result

The complete backend suite passed: **337 tests on isolated PostgreSQL 16.15,
with no skips**, including all 14 contention cases and seven HTTP cases. The
fresh application-process restart retained both the authenticated session and
the original receipt. System checks and missing-migration checks passed.
The test runner stopped its PostgreSQL server and cleaned its temporary cluster.
Syntax, UTF-8 and whitespace checks also passed for the changed implementation.

The initial four HTTP regression cases also passed on isolated SQLite. No shared
database migrations, physical scans, firmware uploads or device-file changes
were performed during this validation.

## Concurrent transactions

`app/attendance/test_pending_concurrency.py` contains 14 PostgreSQL-only tests.
Each uses two independent database connections and a coordinator connection.
The first transaction remains uncommitted until `pg_blocking_pids()` proves the
second operation is waiting on it. Event coordination, bounded waits and database
lock/statement timeouts prevent silent serial execution or indefinite hangs.
No production service or database locking operation is mocked.

The cases exercise:

- Identical imports producing one event and one durable receipt.
- Short/long snapshots arriving in either order, and append versus old-file retry.
- Changed event data rejecting the entire losing snapshot.
- Event UUID reuse across batches leaving no orphan batch.
- Capture/manual UUID collisions in both commit orders.
- Assignment revocation versus import in both commit orders.
- Current academic-session cutover versus import in both commit orders.
- A waiting retry recovering after the first transaction rolls back.
- Interrupted-write review surviving a concurrent clean snapshot.

Successful capture-only cases assert that attendance records/events remain empty.
These are bounded two-worker consistency checks; throughput and sustained load
remain unmeasured. The current calendar singleton still serializes attendance
writes, including imports.

## Real HTTP and process restart

`app/attendance/test_pending_http.py` uses actual HTTP connections, login and
CSRF endpoints, session cookies and original JSONL bytes. Its seven cases cover:

- Preview/import/list, whole-file hash preservation and private response fields.
- Anonymous uploads, missing/invalid CSRF tokens and an untrusted Origin.
- Revoked course access rejecting a request before reading the capture stream.
- UTF-8 content-type parameters preserving the submitted file bytes.
- An HTTP upload ending before its declared length, followed by a complete retry.
- Discarding the successful receipt response body, then recovering the same
  receipt through an exact retry.
- Stopping an application process and starting a fresh process against the same
  isolated PostgreSQL test database, preserving both login and receipt identity.

The fresh-process test requires a database name beginning with `test_`, binds its
HTTP server only to loopback and terminates every process it starts. On SQLite,
the 14 PostgreSQL races and fresh-process restart case are explicitly skipped.
React browser interaction remains pending.

## Integration defect corrected

The HTTP tests exposed a gap in the earlier forced-authentication tests. Standard
DRF session CSRF checking inspected the DRF Request's POST form property, invoking
the intentionally disabled parsers and returning HTTP 415 for authenticated raw
JSONL uploads. The capture endpoints now apply the standard session CSRF check
to the underlying Django HttpRequest. This preserves cookie/header/origin checks
and keeps the body unread until course authorization succeeds. Both negative
CSRF checks and successful uploads exercise that path over HTTP.

Content-type checking now uses Django's parsed media type, accepting an explicit
UTF-8 charset parameter. File decoding remains strict UTF-8 with the same limits.

## Reproduce in an isolated PostgreSQL cluster

Supply an already verified PostgreSQL binary directory:

```powershell
& .\.venv\Scripts\python.exe tools/run_attendance_postgres_tests.py --pg-bin 'PATH_TO_PG_BIN'
```

To run just the new suites, append:

```text
attendance.test_pending_concurrency attendance.test_pending_http
```

The runner creates a fresh cluster beneath ignored `tmp/attendance-postgres-*`,
uses a random loopback port and generated SCRAM password, and runs system checks,
missing-migration checks and the requested Django tests. It stops its server in
cleanup. Successful runs remove only their verified temporary directory; failed
runs retain stopped cluster files/logs for diagnosis. `--keep-cluster` retains
them after success too. No Windows service is installed. Only isolated test
databases receive migrations; the existing application database is not selected.

`config.ci_settings` accepts `POSTGRES_HOST`/`POSTGRES_PORT`, retaining the CI
defaults of localhost/5432. The existing PostgreSQL CI job discovers these tests.

Local execution uses PostgreSQL 16.15 from the
[EDB binary distribution](https://www.enterprisedb.com/download-postgresql-binaries).
The archive `postgresql-16.15-5-windows-x64-binaries.zip` was verified against the
[publisher-provided SHA-256](https://github.com/EnterpriseDB/edb-installers/issues/731):
`43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281`.
The portable runtime lives outside the repository.

## Remaining checks

Physical multi-capture/reboot, storage-full and controlled interrupted-write
power-loss tests still require the connected device and an operator, with
verified recoverable backups. Native/synthetic tests cannot establish electrical
flash-failure recovery. Device contents must be preserved through that work.

Population matching, ambiguous/unknown/out-of-roster identity review, trusted
clocks, reconciliation and 75% metrics need their implementations before their
integration/field tests can run. Device authentication, biometric storage/key
management and retention controls remain unfinished.
