# PostgreSQL integration validation — 21 October 2026

Actual PostgreSQL validation passed against an isolated PostgreSQL **18.6** server on this laptop. No Aiven database or existing local database was used by these tests.

| Check | Observed result |
| --- | --- |
| Django system check | Passed |
| Migration drift (`makemigrations --check --dry-run`) | No changes detected |
| Final backend suite: students, accounts, academics, attendance | **380 tests passed**, 170.383 seconds, no skipped tests reported |
| PostgreSQL concurrency | All 14 independent-connection row-lock contention tests passed |
| Fresh application process | Authenticated session and durable import receipt survived application-process restart |
| Backup/restore with publisher's PostgreSQL 18.6 client | Passed |
| Backup/restore with Aiven-compatible client combination | Passed |
| User-facing `restore-postgres-test.ps1` | Passed; disposable restore and cluster removed |
| Actual Aiven backup restored locally | User confirmed success: **41 tables**; row hashes, constraints and sequences matched |
| Backup safety unit checks | 5 passed |

The final run includes the five deployment-configuration tests and three worker stop-file tests added after the initial 372-test run. All tests ran against a separate fresh PostgreSQL cluster; the existing browser-test cluster on port 12613 was left untouched.

The concurrency tests observe PostgreSQL's actual blocking graph (`pg_blocking_pids`), rather than treating two serial operations as a concurrency test. They cover identical retries, overlapping snapshots, conflicting evidence, UUID collisions, manual/capture races, staff revocation, academic-session cutover and recovery after transaction rollback. The HTTP tests also exercise incomplete uploads, unread success responses and retry after a real application-process restart.

## Reproduce

Obtain the isolated Windows binaries from the publisher if absent:

```powershell
.\.venv\Scripts\python.exe tools\prepare_postgres_runtime.py
.\.venv\Scripts\python.exe tools\run_attendance_postgres_tests.py --pg-bin private-data\postgres18\bin
```

The runner creates a random loopback-only cluster under ignored `tmp/`, generates an independent synthetic password, creates its own database and stops the server in `finally`. It installs no Windows service and overrides inherited PostgreSQL transport settings. Successful runs remove their newly created cluster unless `--keep-cluster` is given. Failures retain logs for diagnosis.

The verified runtime comes from [EDB's PostgreSQL binary distribution](https://www.enterprisedb.com/download-postgresql-binaries), specifically `postgresql-18.6-5-windows-x64-binaries.zip`. The helper fetches selected HTTP ranges, verifies ZIP member CRCs and records local SHA-256 hashes in ignored `private-data/postgres18/manifest.json`. HTTPS to the publisher supplies origin authentication; CRCs alone do not authenticate a download.

## Local evidence

- Final 380-test backend run: stopped cluster/logs at `tmp/attendance-postgres-qkmrha2j/`.
- Initial 372-test backend run: stopped cluster/logs at `tmp/attendance-postgres-xbcf_6fa/`.
- Standard-client backup drill: `tmp/attendance-postgres-4xf8yysb/backup-drill-report.json`.
- Compatible-client backup drill: `tmp/attendance-postgres-0vde4yo_/backup-drill-report.json`.
- Both drills restored **43 tables**, compared **393 constraints** and **33 sequences**, and matched every table's row count and SHA-256 content digest. The source included all migrated Django tables and synthetic Unicode, JSONB, timestamp, bytea, numeric, NULL, identity and foreign-key fixtures.
- A deliberately corrupted archive was rejected before restore.
- Reusable stopped synthetic cluster metadata is in ignored `private-data/postgres-validation/connection.json`; its password is synthetic and must stay out of chat and version control.

The separate compatible client contains current `pg_dump`/`pg_restore` **18.6** executables with official **libpq 16.15** and their dependencies. This handles the Aiven certificate parsing problem observed with the libpq 18 build while retaining `sslmode=verify-full`. The complete local dump/restore drill passed using that combination. Password-free checks against the real Aiven endpoint reached authentication with its correct CA/hostname and rejected an intentionally wrong hostname.

## Actual Aiven evidence and limits

The user has confirmed Aiven migrations, system checks, administrator creation, admin login, and a successful backup followed by a local restore of **41 actual application tables** with matching row hashes, constraints and sequences. The agent did not receive the Aiven password; the authenticated backup and restore were executed privately in the user's configured terminal. The two extra tables in the agent's 43-table synthetic drills are dedicated backup fixtures, which are absent from the Aiven database.

The repeatable procedure is in [backup-restore.md](backup-restore.md). These local tests establish correctness under contention, not a throughput or availability guarantee for Aiven's 20-connection free service. Local restore verification does not replace the live database or establish off-device backup storage.
