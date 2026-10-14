# Remaining project work — 10 October 2026

This inventory is based on active workspace routes/services, not the legacy
portal or historical handoff statements. All 250 backend tests passed against isolated SQLite; migration drift and Django
system checks passed. See backend-lifecycle-guide.md for the latest graduation,
guardian/export and account contracts.

Implemented: custom staff/student sessions and CSRF, HOD admin control, adviser
assignments/scoped student read/create/edit, student own profile, HOD bulk level
changes, academic status, multiple-guardian model/admin, scoped messaging,
academic catalogs/results CRUD-limited-to-score/verification, own verified
results, GPA/CGPA, grading versions and independent adviser academic permissions.

Guardian result sharing now has HOD preview/queue/history/retry APIs, separate
channel permission records, email and Meta WhatsApp adapters, and a durable worker.
See guardian-result-sharing.md. Frontend controls, provider onboarding/template,
worker scheduling and PostgreSQL/live delivery validation remain pending.

## Priorities

1. Shared database integration: source-model comparison, schema mapping comments,
   offline PostgreSQL column reference, read-only inventory SQL and opt-in connection
   settings are prepared in postgres-integration-review.md. Live schema inventory,
   source identity/data reconciliation, tested backups, PostgreSQL validation and
   data conversion/cutover remain pending. Keep the source intact and initially
   migrate a fresh dedicated target. Migrations have only run in isolated tests.
2. CSV pipeline: teammate PDF extraction, representative-layout validation,
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
