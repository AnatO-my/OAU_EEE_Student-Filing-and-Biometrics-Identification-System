# Registration/import integration review — 21 October 2026

The reviewed workflow combines manual adviser registration, bulk student-list
pre-registration, stable student identity and reviewed master-sheet result import.
Implementation tests use synthetic data and isolated PostgreSQL, never Aiven
student data or sending credentials.

## Verified

- Complete backend suite: **416 tests passed on PostgreSQL 18.6** in 219.369
  seconds, with no skips. System checks and migration drift passed.
- The 36 new backend tests cover scoped lookup/registration, absent optional
  contacts, write-only surname, unique canonical identities, preserved UTME
  aliases, promotion/account/result links, migration preservation/collision
  refusal, CSV validation, unknown-student staging, reviewed corrections,
  stale previews, permissions, receipts, retries and atomic rollback.
- Eight new PostgreSQL concurrency tests exercise competing registrations,
  promotion versus registration, repeated/overlapping commits, rollback/retry,
  import versus manual result creation and import versus manual profile edits.
  Import tests observe actual blockers with `pg_blocking_pids`; student tests
  synchronize competing transactions at a barrier.
- Portal **34 tests passed**, ESLint passed and the production build succeeded.
- Existing standalone guardian suite: **13 tests passed**.
- Structured master-sheet adapter: **5 tests passed**, including leading zeros,
  decimal scores, zero/NG handling, duplicate reporting, trace/count reconciliation
  and refusal to overwrite output.
- PowerShell update helper syntax and `git diff --check` passed.
- Browser check on isolated synthetic PostgreSQL: HOD login, identifier check,
  registration without a phone/login account, CSV preview, reviewed result commit
  and receipt recovery through history succeeded. Proof:
  `output/local-integration/import-receipt.png`.
- A final NUL-character guard for correction reasons passed the focused
  **17-test import suite** after the complete run above.

The first complete PostgreSQL run found six fixture errors because transaction
tests clear data-migration rows. The import tests now explicitly create their
grading scale and mutex fixtures. The final complete run above includes that fix.
The review also corrected import/manual-edit lock ordering before final validation.

## Converter integration follow-up — 22 October 2026

The reported failure was `sample_students.csv`: the converter exports one student
per row with JSON course lists, while the original importer required one result
per row. The portal now recognizes the existing converter's student/table CSV
formats and supported native master-sheet PDFs, reusing packaged extraction,
student parsing and CSV adaptation code. The command-line entry points remain
compatible. Conversion requires reviewed attempt/context and extraction review
before database matching; the saved batch still contains only the normalized CSV.

Validated after this change:

- **36 import tests passed on PostgreSQL 18.6** in 27.476 seconds, including
  13 new preparation tests and the existing import/concurrency tests. System
  checks and migration drift passed. The disposable cluster was stopped; logs
  remain in `tmp/attendance-postgres-rm7nlz2p`.
- **39 portal tests passed**, ESLint passed and the production build succeeded.
- The original **10 student-parser tests** and **5 adapter tests** passed.
  A synthetic native PDF also passed the unchanged CLI workflow.
- Synthetic nested CSV, raw table CSV and actual native PDF preparation produced
  identical normalized CSV. Review caught and fixed integer page/table prefixes
  before passing them to the existing string-cell parser.
- Browser check on isolated synthetic PostgreSQL: nested converter CSV prepared
  successfully, required extraction review, then showed an existing mark as
  **Already recorded**, with zero new students/results. No commit was requested.
  Proof: `output/local-integration/converter-reimport.png`.
- Read-only preparation of the user's existing local `output/sample_students.csv`
  recognized 860 course entries: 575 accepted, 270 unresolved marks and 15 literal
  zero marks requiring source confirmation. No database preview/import was
  requested for that file, and no personal record values were printed.

The complete 416-test run above predates this follow-up; the focused 36-test
PostgreSQL suite is the validation for the converter change. No additional schema
migration is required. Restart the local launcher from the configured terminal
so Django loads the new endpoint, then refresh the browser.

## Results-only workflow clarification — 22 October 2026

The user chose to keep student registration separate and hold results for unknown
matriculation numbers. The portal now labels the workspace **Upload results**,
with one conversion/matching action, a visible reviewed-attempt field and a single
final review before commit. Session, semester, course and mark fields are read
from the supported sheet; missing context is supplied only when needed. The
result workspace has no student intake mode or student-creation counts.

Validated for this clarification:

- **38 import tests passed on PostgreSQL 18.6** in 40.582 seconds. System and
  migration-drift checks passed. The isolated cluster was stopped; logs remain
  in `tmp/attendance-postgres-cvlzkw5e`.
- **44 portal tests**, ESLint and the production build passed. Tests cover the
  one-action pipeline, result-only access/history, held unknown students,
  explicit attempt context, correction review and uncertain-outcome recovery.
- A mixed result batch containing an unknown student stayed blocked without
  creating any student or result. Separate registration followed by refresh
  then allowed the reviewed result commit.
- The browser accepted a real synthetic native PDF, converted it and matched
  its scores in one action. Course/session/semester/score fields came from the
  PDF without manual context. An existing score showed **Already recorded**.
  No commit was requested. Proof:
  `output/local-integration/results-only-upload.png`.

The history endpoint now supports owner-scoped `kind=results|roster` filtering
before pagination. Existing backend roster data/contracts remain available to
existing integrations, separate from the result-only portal workspace. No schema
migration or Aiven data change is needed for this clarification.

## Laptop activation

The user confirmed that the updated portal works and that the student registration
control is usable. The checks below describe the activation helper; the agent
does not have the user's configured Aiven terminal or its database password.

On 22 October 2026 the user also confirmed the account-administration update and
visible staff, part-adviser and HOD-transfer controls after restarting. See
[the current account checkpoint](account-administration.md) for the audit
migration and 447-test backend / 63-test portal validation.

The two new schema migrations are `students.0007_student_identifier_registry` and
`record_imports.0001_initial`. They must be applied in the user's configured Aiven
terminal, after stopping existing local servers/workers. The agent does not have
that terminal's database password and has not migrated Aiven or imported students.

`scripts/update-local.ps1` checks the connection, displays the plan, creates a
new timestamped backup and verifies a local restoration, applies migrations,
checks the database and starts the local application. It creates no login
accounts and imports no students/results. A legacy identity collision stops
migration atomically for explicit review instead of merging records.

See [student registration](student-registration.md), [import contracts](student-result-imports.md),
[PDF adapter](pdf-student-extraction.md) and [laptop startup](local-laptop.md).
