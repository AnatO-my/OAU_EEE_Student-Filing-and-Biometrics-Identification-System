# Remaining project work — 14 October 2026

## Database checkpoint — 21 October 2026

Aiven Free PostgreSQL 18.6 is connected with verified TLS. All 38 migrations,
the standard student-access groups and the initial administrator are set up;
the user confirmed migration/system checks and administrator dashboard login.
Anonymous HTTP checks passed for CSRF, the admin login page and denied access
to protected identity/student endpoints. The integrated React portal is now in
`frontend/portal`, with laptop startup in `scripts/start-local.ps1`. All 380
backend tests passed on isolated PostgreSQL 18.6, including contention and
process-restart checks. The user also verified an actual Aiven backup restored
41 tables with matching row hashes, constraints and sequences. See
[Aiven integration setup and verification](aiven-free-postgresql.md), including
the compatible Windows client configuration, plus the
[laptop run guide](local-laptop.md), [frontend checkpoint](frontend-integration-checkpoint.md),
[PostgreSQL test checkpoint](postgres-validation-checkpoint.md) and
[backup restoration procedure](backup-restore.md). Portal lint/build, 18 portal
tests and 13 guardian tests pass. Application/worker hosting is deferred at the
user's request; the local worker remains an explicit delivery option. Real-data
import, remaining admin-only workflows and physical biometric integration are
separate outstanding work.
The historical inventory below retains its earlier dates and test counts.

Student first-login setup — 22 October 2026: the HOD can issue a linked login
from **Student login** on a student record. The student chooses the password
through a private one-time link, with no SMTP dependency. Reissue/expiry/replay,
fresh HOD authorization and PostgreSQL concurrency checks passed. The full
backend suite passed 466 tests; the portal passed 83 tests, lint and build.
Synthetic HTTP/browser checks verified student sign-in, own profile and verified
result access, with staff directory access denied. No new migration is added
after the existing account audit table. Laptop activation uses an app restart;
the user confirmed successful student first login. The subsequent email-access
and exact-matriculation username update passed 486 PostgreSQL tests and 104
portal tests, lint and build. It adds the metadata-only
`accounts.0006_user_username_matriculation` migration, explicit reviewed account
updates and SMTP setup/reset links without emailing passwords. Existing names
do not change automatically. Actual email receipt is a pending user-side check.
See [student accounts](student-accounts.md).

Account administration activation — 22 October 2026: the user confirmed the
update/restart and visible staff, part-adviser and HOD-transfer controls under
profile-linked Account settings. The complete updated backend suite passed
447 tests on isolated PostgreSQL; 63 portal tests, lint and build passed. See
[account administration](account-administration.md) and
[the blue portal redesign](portal-design-checkpoint.md). No real ownership
transfer was performed during implementation verification.

Workflow clarification — 22 October 2026: the portal now separates student
registration from **Upload results**. Master-sheet PDF conversion fills result
fields and matches existing students. Unknown matric numbers hold the batch until
staff register the student separately and refresh it. Results never create
incomplete student records. Conversion and matching share one preview action;
the existing correction/verification rules remain. This change needs a restart,
with no additional schema migration.

The subsequent registration/import update adds scoped adviser registration,
optional missing contact details, canonical identifier uniqueness and retained
UTME aliases, reviewed bulk student lists and result CSV imports with conflict
approvals, atomic commit and durable receipts. The full updated backend suite
passes **416 tests on PostgreSQL**, and portal tests/build/lint pass (**34 tests**).
See [the review checkpoint](registration-import-validation.md). Two new migrations
must still be applied from the configured Aiven terminal before using these new
workflows there; no departmental students have been automatically imported.

This inventory is based on active workspace routes/services, not the legacy
portal or historical handoff statements. All 280 backend tests passed against isolated SQLite; migration drift and Django
system checks passed. See backend-lifecycle-guide.md for the latest graduation,
guardian/export and account contracts.

Implemented: custom staff/student sessions and CSRF, HOD admin control, adviser
assignments/scoped student read/create/edit, student own profile, HOD bulk level
changes, academic status, multiple-guardian model/admin, scoped messaging,
academic catalogs/results CRUD-limited-to-score/verification, own verified
results, GPA/CGPA, grading versions and independent adviser academic permissions.

Guardian result sharing now has HOD preview/queue/history/retry APIs, separate
channel permission records, email and Meta WhatsApp adapters, and a durable worker.
See guardian-result-sharing.md. A separate React email page and email-only polling
worker are implemented; startup/merge instructions are in
../frontend/guardian-results/README.md. The user confirmed Gmail mock receipt.
Production worker activation, WhatsApp onboarding/template, PostgreSQL concurrency
validation and institutional delivery validation remain pending.

## Priorities

1. Shared database integration: source-model comparison, schema mapping comments,
   offline PostgreSQL column reference, read-only inventory SQL and opt-in connection
   settings are prepared in postgres-integration-review.md. Live schema inventory,
   source identity/data reconciliation, tested backups, PostgreSQL validation and
   data conversion/cutover remain pending. Keep the source intact and initially
   migrate a fresh dedicated target. Migrations have only run in isolated tests.
2. CSV pipeline: the user reports a teammate has implemented the importer;
   combining and validating that implementation is deferred. Remaining integration
   must review representative-layout validation,
   backend preview/error reporting, all-or-nothing import, safe re-import and
   source provenance. See csv-extraction-teammate-guide.md.
3. Academic completeness/graduation: implemented an HOD-reviewed required-offering
   manifest, reasoned transfer/exemption resolutions, current-history approval and
   verified unrounded CGPA >=1.00 for atomic individual/bulk graduation. Automatic
   curriculum rules, real-data review and deferred academic warnings remain pending.
   HOD review is the agreed initial completeness authority.
4. Original staff requirements: guardian read/create/update APIs and scoped profile
   CSV export are implemented. Export requires students.export_student independently
   of read/edit; the initial column policy excludes guardians, accounts and biometrics.
   React screens and real-browser integration remain pending.
5. Account lifecycle and frontend: password change/reset, HOD student-account
   creation/linking and effective permission/role information are implemented.
   Cookies/CSRF use a same-origin API proxy. Configure an HTTPS reset page, SMTP
   delivery and shared throttle cache before production; React pages and live
   browser/mail end-to-end checks remain pending.
6. Biometrics: validate actual board/sensor capabilities for server-side matching,
   enrollment/template storage/matcher, device authentication, scan endpoints,
   feedback, retry deduplication and integration tests. Referenced attendance
   firmware performs sensor-side matching; see biometric-repository-review.md.
   Attendance foundation is implemented locally: approved course roster snapshots,
   explicit course staff, manual class attendance, duplicate handling, corrections
   and own-student record APIs. Database current-session selection is available to
   HOD in admin/API. Biometric capture, device authentication, offline sync and
   attendance reporting remain pending; see attendance-api.md.
7. Audit and operations: record result edits/verification/imports, profile changes,
   bulk transitions and permission changes; production database/backups/restore,
   deployment configuration, monitoring and permission regression testing.
8. Repository checkpoint and team handoff: backend changes are prepared on
   codex/backend-academics-result-sharing, based on main through PR #11.
   Obtain required review and PostgreSQL CI checks before merging.
   No merge/deployment is implied by local passing tests.

Document/file upload storage and an attendance/class-session subsystem need an
explicit agreed scope if they are to be adapted from either external repository.
Neither should be silently introduced by copying a legacy project's models.
