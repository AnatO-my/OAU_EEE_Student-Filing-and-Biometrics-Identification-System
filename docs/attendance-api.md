# Attendance foundation — 14 October 2026

Implemented: approved course rosters, explicit course-staff assignments, class
sessions, manual attendance, retry deduplication, correction history and private
student attendance records, plus authorized pending USB batch preview/import.
Fingerprint matching, authenticated device submission, offline authorization and
React screens are pending.
No scan endpoint accepts an arbitrary student UUID as biometric proof.

## Current academic session

The HOD can add an academic session in Django admin, select it in the academic
session list, then run Set the selected academic session as current. Alternatively:
GET/PUT /api/academic-sessions/current/ (HOD only).
PUT requires academic_session (catalog ID) and expected_session_id (the ID returned
by GET, null before the first database selection). Stale updates are rejected.
Selection changes are recorded. Session names cannot be edited through admin;
create another catalog session instead of rewriting assignment references.

The database selection overrides CURRENT_ACADEMIC_SESSION across adviser scope,
messaging, effective adviser levels and academic permissions. The environment
value remains a bootstrap fallback until the first selection. Changing the current
session does not advance levels, copy assignments, open classes or rewrite results.
HOD must separately review new-session course/staff assignments and rosters.

## Course preparation

HOD PUT /api/attendance/offerings/{offering_id}/staff/:
{"staff": 12, "is_active": true}. IDs are illustrative only. Course assignments
are independent of adviser-level assignments. Grant ordinary staff these Django
permissions as appropriate: attendance.view_attendance, manage_attendance,
record_attendance and correct_attendance. Assignment alone grants no action.

HOD GET /api/attendance/offerings/{offering_id}/roster/ returns paginated candidate
students, suggestion reasons, confirmed_revision and confirmed_student_ids.
Candidates are active undergraduates at the offering's level plus students whose
latest verified, scored attempt in the course before the target period has zero
grade points under its saved grading version. A later verified pass removes the
retaker suggestion. This is a suggestion, not a current registration assertion.
Unverified attempts and missing scores are not used to infer retakers. HOD must
check current registration/exemptions and can add or remove active undergraduates.

HOD PUT the same roster URL with student_ids (1–1000 unique UUIDs) and
expected_revision (0 for the first confirmation). Confirm once for the course
session/semester; each class snapshots the approved list and its revision.
Every confirmation preserves its membership and confirming HOD in history.
Subsequent roster/level changes do not rewrite already opened class rosters.
An inactive or graduated student cannot receive a new manual attendance mark.

## Classes and recording

GET/POST /api/attendance/sessions/. POST accepts offering, title, starts_at and
ends_at as timezone-aware ISO-8601 datetimes. The end must follow the start, the
offering must be current, and a confirmed roster is required. New classes are open;
recording is restricted to the inclusive start/end window until explicitly closed.
List endpoints use 20-row pagination. Unassigned staff see no course records.

GET /api/attendance/sessions/{uuid}/ returns class details and roster IDs to
permitted staff. POST .../close/ closes it idempotently. Closing does not delete
history; no reopen/cancel endpoint is implemented in this foundation.

GET/POST .../records/. POST accepts student (UUID), event_id (new UUID), reason
(nonblank, at most 1000 characters). This is authorized MANUAL recording with
server time, not fingerprint proof. Each class/student has one attendance record.
A second event is duplicate=true and does not toggle or overwrite the record.
An identical event retry returns replayed=true; changing its actor/student/class
or reason is rejected. Authorized exact retries still work after closure; new
submissions do not. Revoked staff cannot use retries to bypass current access.

POST /api/attendance/records/{id}/correct/ accepts status (present or absent) and
reason. Only HOD/assigned staff with correct_attendance may correct. Actor, time,
old/new status and reason are retained separately from original submission events.
Duplicate submissions cannot undo corrections. No delete endpoint exists.

GET /api/me/attendance/ returns only the logged-in linked student's recorded
attendance. It does not expose another student's rows, reasons or staff identities.
Roster members without a record are NOT yet rendered as absent automatically.
Absence summaries, late/excused rules, percentages and export remain a later step;
no departmental minimum attendance percentage has been assumed.

## Integration and verification

Pending USB batches now have authorized preview/import and metadata-list routes.
See [attendance-pending-batches.md](attendance-pending-batches.md) for access,
raw JSONL uploads, preview digests, immutable retries and durable receipts.
Imports remain unidentified evidence; identity/timing review and reconciliation
must precede attendance writes. No raw biometric read/export route is provided.
The real session/CSRF HTTP path and PostgreSQL contention now have integration
coverage; see [attendance-validation.md](attendance-validation.md).

All API writes use existing Django session/CSRF authentication. Admin attendance
screens are HOD-only and read-only, preserving service validation and audit paths.
Production database concurrency has not been stress-tested. Attendance writes
serialize through the current-session singleton before row locks; this prevents
current-session switches racing with attendance writes but limits write throughput.
The existing adviser/profile services resolve the current session without this
attendance serialization; their concurrent session-cutover behavior needs review.

Migrations academics/0006 and attendance/0001–0003 are generated. They have only
run in isolated tests. Do not apply them to the shared/legacy database before the
agreed schema reconciliation. The development database was not migrated.
The result importer remains teammate-owned and will be combined separately.
