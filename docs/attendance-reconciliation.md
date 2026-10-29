# Attendance capture reconciliation

These features are API-only; browser attendance controls and the live hardware bridge remain to be integrated. The staff API retains existing roster approval, per-course assignments and meeting UUID validation. Each JSONL file remains attached to its declared lecture meeting; boot elapsed milliseconds are not treated as a calendar timestamp.

New migrations: `attendance.0004_capturereview_scannerreference`, `attendance.0005_meetingfinalisation`, `attendance.0006_meetingfinalisation_excusals_snapshot_and_more` and `attendance.0007_attendanceexcusal_eligibility_roster_revision_and_more`. Apply normal deployment migrations before using these endpoints. No production database is migrated by the tests.

## Staff workflow

1. Preview and import the bounded JSONL using the existing pending-batches endpoints and SHA-256 confirmation. No student is marked present by import.
2. GET `/api/attendance/sessions/{meeting_uuid}/captures/` for a paginated metadata-only queue. Unreviewed deferred captures are archived with no expiry, including historical imports. Probe bytes are never returned.
3. POST `/api/attendance/captures/{capture_uuid}/review/` with `{"mode":"deferred"}` when staff choose an archived capture for resolution. For a live capture review use `{"mode":"live"}`; it becomes flagged. Once selected, the mode is fixed.
4. POST `/api/attendance/captures/{capture_uuid}/resolve/` with `student` (registered student UUID), `timing_confirmed:true`, and a substantive `reason` describing the identity and meeting evidence reviewed. This is an explicit staff decision, not an automatic biometric match. The meeting and approved roster cannot be changed. Closed meetings can be reconciled later. The exact retry is idempotent; another capture for the same student cannot add another presence. Existing absent records must first use the established audited correction endpoint.

Review/import needs the dedicated import permission, viewing needs the existing course visibility, and resolution needs the existing correction permission and active course assignment. Inactive/unassigned staff are rejected. Superuser access retains the established policy. Review rows record who selected and resolved the capture and the reason; original probes remain immutable and protected from deletion.

## Scanner reference mapping

POST `/api/attendance/sessions/{meeting_uuid}/scanner-references/` with `student`, `scanner_uuid` and `reference_id` records an enrolled scanner slot/reference against a registered student's UUID. Their current matric number is obtained through the student relation; it is not a second independent identity. A scanner slot cannot be silently reassigned. This endpoint registers administrative metadata only: it neither enrols a finger on hardware nor uploads reference template bytes. It currently requires an approved meeting roster and staff recording permission.

## Course rates

GET `/api/attendance/offerings/{offering_id}/rates/` returns, per roster student, distinct meetings attended, eligible recorded meetings, pending meetings and a two-decimal percentage (null when denominator is zero). Open meetings are excluded. Closed meetings use their immutable roster snapshot. Without a current explicit finalisation, an empty pending batch, a batch requiring interrupted-write recovery review, or any unresolved captured identity defers the entire meeting for all roster members. A closed meeting becomes eligible when those issues are reconciled OR staff explicitly finalise the reviewed meeting as described below. Unmarked roster members then contribute zero attendance; unknown captures themselves never create attendance records. The response exposes pending counts, `finalised_meetings` and `stale_finalisation_meetings` so provisional and reviewed states remain visible. Repeated scans never increase the numerator. Formal excuses remove the meeting from BOTH the numerator and denominator for the named student, even if a confirmed present record exists. `excused_meetings` counts excused closed meetings in the fixed roster, including pending or finalised meetings. Pending/finalised/stale counters still show the source state, so these counts can overlap the excused count. Open meetings are excluded from all these rate counts. A zero denominator returns null.

## Present/absent and formal excuses

Attendance statuses remain only `present` and `absent`. There is no late category or time-based late penalty. Temporal information attaches context to the bound lecture meeting; boot elapsed milliseconds do not establish a calendar timestamp. Explicit timing confirmation remains required when resolving captured evidence.

GET `/api/attendance/sessions/{meeting_uuid}/excusals/` lists the current formal excusal metadata. POST that endpoint to grant or revoke:

```json
{
  "student": "<registered student UUID in this meeting roster>",
  "event_id": "<new UUID idempotency key>",
  "is_excused": true,
  "reason": "Formal excuse reviewed by assigned staff"
}
```

Use `is_excused:false` and a new event UUID/reason to revoke; use another new UUID to grant again. Assigned course staff approve formal excuses directly. A written reason is sufficient: no HOD preapproval and no supporting-document upload are required. The existing access configuration still applies: the account must be active staff, actively assigned to this course offering in the current academic session, with `attendance.view_attendance` for meeting visibility and `attendance.correct_attendance` for the excusal decision. These permissions are already available in the supported staff-administration permission options and can be granted directly or through an existing group. Course assignment alone grants no action. Provisioning access is separate from approving individual excuses; an authorised course staff member does not submit each excuse to the HOD. Open and closed meetings support this deliberate decision. Every state change records the reviewer, timestamp, reason and before/after decision in a separate append-only audit. Normal excuses use the fixed meeting roster; the explicitly scoped late-registration exception below preserves that roster. Reasons are nonblank with a 1,000-character bound.

The exact same event retry returns the original receipt without reapplying it. Reusing an event UUID for another student, meeting, actor, state, reason or retrospective scope is rejected. A later retry of an old grant after revocation returns `current_is_excused:false`, preserving the revocation. A new UUID requesting an unchanged state is rejected rather than producing duplicate audit. Excusal never erases or rewrites attendance records, captured probes, or their reviewed identity evidence.

## Future roster changes and retrospective late-registration excuses

A later HOD-approved course roster affects meetings opened afterward. Existing meeting `student_ids` and `roster_revision` remain unchanged; new roster members do not automatically acquire past absences, presence or rate-denominator eligibility.

For a later-registered student, staff may explicitly record a written formal excuse against an earlier meeting without changing its historical roster. Use the same excusals endpoint and add an explicit scope flag:

```json
{
  "student": "<student UUID on the current approved course roster>",
  "event_id": "<new UUID>",
  "is_excused": true,
  "retrospective": true,
  "reason": "Registered late; the earlier meeting is formally excused"
}
```

The student must be outside that meeting's immutable snapshot and belong to the current HOD-approved roster for the same course offering, at a later roster revision. An arbitrary outsider cannot receive this exception. Ordinary historical-roster excuses use `retrospective:false` (the default); an existing excusal cannot switch scope. This uses the same assigned-staff correction authority and written reason, with no per-excuse HOD preapproval or supporting-document requirement.

The response, list and finalisation preview show `retrospective`, `historical_roster_member` and `eligibility_roster_revision`. Each action preserves the authorising course-roster revision in its audit; subsequent roster changes do not rewrite that evidence. New grants/regrants require current approved membership. An exact old retry and explicit revocation remain possible after later roster removal; neither re-establishes membership or re-applies an old grant.

Rates expose active outside-snapshot excuses in `retrospective_excused_meetings` for closed meetings. This count is separate from `excused_meetings`: the original meeting denominator and numerator remain untouched because that student was never historically eligible. A student with only retrospective excuses can appear with zero eligible meetings and a null percentage. Future meetings count normally once opened with the updated roster. Revoked retrospective excuses remain in the audit/list but stop contributing to the active retrospective count.

No attendance record or biometric identity match is created by this exception. Existing capture resolution and manual presence still enforce historical meeting membership. Formal finalisation review digests/snapshots include retrospective excuse metadata, so concurrent decisions require review again; later audited decisions can update the informational count without rewriting the earlier approval.

## Explicit meeting finalisation

Closing collection and finalising reviewed attendance are separate actions. Closing or importing alone never authorises treating unresolved captures as reviewed. Finalisation is optional for closed fully reconciled/manual meetings; it is required to include a meeting while unmatched, empty or recovery-flagged evidence remains archived.

1. GET `/api/attendance/sessions/{meeting_uuid}/finalisation/`. Review `confirmed_records`, `confirmed_excusals` and the meeting's capture queue. The response includes `review_sha256`, `evidence_sha256`, `finalised`, `review_stale`, `revision`, reviewer/time/reason `last_reviewed_records` and `last_reviewed_excusals`.
2. POST the same endpoint with the current review digest:

```json
{
  "expected_digest": "<review_sha256 returned by GET>",
  "reviewed": true,
  "reason": "Reviewed confirmed attendance and retained unmatched captures in the archive"
}
```

Only active, assigned staff with `attendance.correct_attendance` and normal meeting visibility may use this endpoint; established superuser access is retained. Collection must already be closed. An explicit confirmation and nonblank reason are required. The expected review digest binds source evidence, current confirmed records and formal excusal state/action metadata; concurrent changes require another GET/review. An exact successful retry returns `replayed:true` without another audit row.

Each append-only finalisation revision records reviewer, timestamp, reason, fixed roster UUIDs, the confirmed-record snapshot and the formal-excusal snapshot. It also binds the source meeting, roster revision/window, batch metadata, capture identifiers/byte hashes, import receipt hashes and recovery flags. New imports or changed source evidence invalidate that finalisation: `finalised:false`, `review_stale:true`; unresolved meetings then return to pending until explicitly reviewed again. Retrying the exact previously accepted import does not invalidate anything.

A valid finalisation permits rates based only on confirmed present records while unknown probes remain archived indefinitely. It does not identify those probes, clear recovery warnings, create attendance records, send notices or delete evidence. Staff may later deliberately resolve archived captures, use audited attendance corrections, or grant/revoke formal excuses. Those audited decisions update the numerator/denominator/rate without invalidating source-evidence approval; `last_reviewed_records` preserves the earlier decision snapshot. An older exact finalisation retry returns its existing receipt rather than recording a new approval of changed records.

## Hardware limitation

No compatible AS608 probe/reference matcher or authenticated live scanner transport is implemented here. The review endpoints support staff decisions for imported evidence and live flagged review state; they do not prove identity or trustworthy capture time. Staff must confirm these from independent evidence. Deferred probes remain archived indefinitely until selected and resolved; there is no automatic expiry or automatic presence from unresolved files. Meeting inclusion with unresolved evidence requires explicit staff finalisation. Future matcher integration must preserve source evidence, compatibility checks, meeting binding and audited resolution.

Validation uses synthetic probe bytes with `python manage.py test attendance --settings=config.test_settings --noinput`; no real scanner, private biometric files, live database or emails are used.

## Course thresholds, finalised-only exam eligibility and exceptions

The connected Attendance page now has on-demand controls for course policy, exam exceptions, capture review/resolution, finalisation, normal/retrospective excusals and biometric reference mappings. The student page can show only that signed-in student's exam attendance summary. Scoped session metadata includes student names/matric identifiers for human choices; other-course staff and peer students cannot inspect those records.

Ordinary `/rates/` retains its previous provisional/conservative calculation. Exam eligibility is separate and uses **only closed meetings with a current source-evidence-valid explicit finalisation**. Mere closing/importing/manual presence is never enough for an exam decision. Stale source review removes that meeting from the exam denominator until re-finalised. Formal excuses exclude both numerator and denominator; retrospective metadata still does not create historical eligibility. No finalised denominator or no configured threshold means `unknown`, not failure. API results identify the finalised-only basis and pending counts.

GET/PUT `/api/attendance/offerings/{offering_id}/eligibility/` lists scoped student exam decisions or appends a threshold revision using event_id, minimum_percentage (0–100) and a written reason. Course-assigned staff with the established correction capability choose the threshold discretionarily. No department-wide percentage is silently imposed. Below-threshold students are flagged and `exam_allowed:false` unless an explicit exception applies.

POST `/api/attendance/offerings/{offering_id}/exam-exceptions/` uses student UUID, event_id, enabled and written reason. Assigned correction-authorised staff or HOD may approve/revoke; actions preserve actor/time/reason. Exact UUID retries do not duplicate decisions, and changed payload reuse is rejected. An approved exception is labelled `exception_approved`, distinct from calculated eligibility, including when source data is insufficient. These are website exam-permission decisions; no external examination-registration platform is contacted.

GET `/api/me/attendance-eligibility/` computes only the authenticated student's rows. It accepts no client-selected student or administrative impersonation. Staff course outputs remain assignment-scoped and HOD retains department access.

## Staff biometric reference enrolment/replacement and manual inability

Migration `attendance.0008_attendancepolicyrevision_examexceptiondecision_and_more` adds policy/audit and active scanner-reference history. Provision `attendance.manage_biometric_reference` to authorised staff, normally advisers. The staff member may enrol students within their active adviser-level or assigned-course scope, without gaining broader private-profile rights. HOD oversight remains. GET `/api/attendance/biometric-students/` supplies only scoped names/matric identifiers; GET/POST `/api/attendance/biometric-references/` lists mappings or creates one using student, scanner_uuid, reference_id and optional replaces reference ID. Replacement disables the old mapping with actor/time and links its replacement; bytes/history are not deleted, and a disabled mapping is not reactivated by retry. Only one active mapping can own a scanner slot.

The server explicitly returns `hardware_enrolment_performed:false`. The available `hardware/fingerprint-diagnostic` firmware/CLI can physically enrol/export/restore and perform AS608-assisted diagnostic matching, but it is not an authenticated application bridge. No compatible application matcher or trusted live scanner transfer is claimed. Physical enrolment must occur on the configured scanner before its reference metadata is linked; physical board/port and compatibility validation remain separate from synthetic tests.

Temporary or ongoing inability to provide a working fingerprint uses the existing reason-backed manual attendance path during the meeting recording window, or the existing audited correction/reconciliation workflow afterward. No fingerprint record is required for manual attendance, and no late penalty is inferred from elapsed device time.
