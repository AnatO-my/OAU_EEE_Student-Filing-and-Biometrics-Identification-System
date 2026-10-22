# Attendance implementation plan — 14 October 2026

Approved decisions: course-offering sessions; one attendance record per student;
HOD and explicitly assigned course staff manage sessions/corrections; candidates
combine students at the offering level and latest verified failed attempts for
HOD review. HOD confirms one roster per offering/session/semester, then individual
class meetings use snapshots of that list.

Implemented locally: database-managed current academic session, roster proposal
and confirmation history, course-staff assignments, manual class attendance,
duplicate/retry protection, corrections and own-student record views. On
16 October, authorized pending USB capture preview/import, immutable events,
append-only batch snapshots and durable receipts were added locally. See
[attendance-pending-batches.md](attendance-pending-batches.md).
See attendance-api.md for routes, permissions and validation boundaries.

Remaining steps:
1. Define restricted enrollment-to-student bindings and reviewed scanner-assisted
   matching. Saved-probe direct comparison has passed on the verified AS608;
   population matching and software-only matching are not established.
2. Reconcile resolved, eligible identities through attendance services with audit
   history and one record per student/class.
3. Provision a trusted clock/RTC. Captures currently retain null wall-clock time,
   boot UUID and elapsed milliseconds; timing review remains mandatory.
4. Implement completed/reconciled class metrics, cancellation and excused states,
   and 75% warnings without counting pending reconciliation as absence.
5. Authenticate devices/laptops, add bounded offline authorization, connect React
   and run sustained-load and physical field tests. Bounded PostgreSQL contention
   and session-authenticated HTTP/restart tests now pass; see
   [attendance-validation.md](attendance-validation.md).

Result-importer integration is deferred for combining the teammate's implementation.
The importer was tested with synthetic payloads on isolated SQLite and PostgreSQL.
No development/shared database migrations or new physical scans were performed
during the backend import implementation.

## Device requirements confirmed on 16 October 2026

Offline attendance will capture unidentified probes and match later. The initial
warning threshold is configurable at 75%, excluding formally excused classes.
See attendance-device-workflow.md for pending capture/import/matching, reporting
and filtered exam gallery deployment contracts. No device capture/import feature
is implied by the existing manual attendance APIs.
