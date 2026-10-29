# Teaching communication, course materials and timetable

The connected live portal now has Messages, Course materials and Timetable pages. Earlier adviser/HOD messages retain their existing inbox/routes and appear in the separate Earlier messages section. This app does not migrate or overwrite legacy communication.

## Access and provisioning

Register `teaching.apps.TeachingConfig` and include `teaching.urls` under `/api/` (already integrated in this checkout). Apply generated migrations through the normal deployment procedure; these implementation tests do not migrate the live database. Provision `teaching.publish_message`, `teaching.manage_material` and `teaching.manage_timetable` through staff administration as appropriate. Course assignment is separate from capabilities. HOD retains departmental oversight; staff materials/timetable access is restricted to their active current-session course assignments. Student course access uses the current HOD-approved roster.

## Messages

- GET/POST `/api/teaching/messages/`: list latest authorised messages or publish directly. No approval queue.
- GET/PUT `/api/teaching/messages/{uuid}/`: explicitly open the latest message (recipient opening records read), or author publishes a new version. Listing and link notification do not mark read.
- GET `/api/teaching/messages/{uuid}/history/`: author-only version/read/notification audit.
- GET `/api/teaching/audience-options/`: publish-authorised staff only, minimal name/matric/account identifiers for human recipient pickers. It exposes no email, phone or private documents.
- GET `/api/teaching/courses/`: course labels within the caller's enrolled/assigned scope.

Publication JSON uses `event_id` UUID, `subject`, `body`, `audience`, `expected_version` (0 for new) and `withdrawn` (false by default). Audience supports students/staff booleans, specific student UUIDs/staff account IDs, optional level and course-offering filters. Students require active linked portal accounts; recipients are snapshotted per version, not silently added later. Course-filtered publishing requires sender course assignment. General messages may be published by authorised staff to the selected departmental audience.

Edits create another version with unread receipts, preserving older content and read timestamps. Only the original author revises/withdraws their message. Withdrawals create a redacted latest version and a short notice for prior recipients; earlier content/read history remains in author audit. Removed recipients do not gain access to revised private content. The UI offers names rather than requiring raw IDs and highlights a link-selected message without opening it automatically.

## Link notification outbox

Each message version/recipient has one durable outbox row. Publication queues rows but does not send email inline. Configure actual email settings and `TEACHING_PORTAL_URL` to the deployment's absolute portal URL. Development defaults to `http://127.0.0.1:5175/portal`; production must configure it explicitly. The URL must be a trusted HTTP(S) base without credentials, query or fragment; invalid/unconfigured bases stop before any send attempt. Run the supervised worker periodically/as an explicit deployment job:

```powershell
python manage.py send_teaching_notifications --limit 100
```

Emails contain a generic new-message/withdrawal notice, website link and sign-in instruction. They contain neither message body/subject, private student documents nor attachments. The worker rechecks current message version, active account, snapshotted email address, publisher capability and current filtered audience. Superseded or no-longer-eligible pending notifications are skipped. A stable Message-ID and one-to-one receipt prevent duplicate publication queues; exact request retries preserve the same version.

The worker persists `sending` before external mail. An exception or non-one send result becomes `unknown`, never automatically retried. A process interrupted while sending remains `sending` and also is not automatically retried. Operator/provider reconciliation is required for uncertain outcomes; no speculative resend occurs. A provider could accept a notification immediately before a concurrent revision/withdrawal commits, so its link always resolves the current authorised website version. Email acceptance is not proof that the recipient read the website.

## Course materials

GET/POST `/api/teaching/materials/`; PUT `/api/teaching/materials/{uuid}/` replaces/withdraws. GET the item is an assigned-staff version archive; download uses `/api/teaching/materials/{uuid}/versions/{version}/download/`. Multipart fields: event_id, offering, title, reason, upload, expected_version, withdrawn. Every replacement/withdrawal is another immutable version; old bytes remain private. Students may download only the latest non-withdrawn version while still on that course's approved roster; assigned staff can audit retained versions. No public file URL is exposed.

Uploads are bounded to 20 MiB, with PDF/text/CSV/Office extensions and basic PDF/Office signatures. Downloads are attachments with no-store responses. This is not an antivirus or document-content scanning service; production upload/transport limits remain part of deployment configuration. Exact UUID+payload retries reuse the existing version.

### Material upload/download correction - 26 October

A focused HTTP test reproduced a download failure: the portal's generic binary-file adapter sent `Accept: text/csv`, and a material download returned HTTP 406 before streaming the file. Binary downloads now send `Accept: */*`; JSON API calls retain their JSON Accept header. This also avoids the same content-negotiation fault for other private document downloads.

Successful uploads, replacements and withdrawals show an explicit confirmation. The upload form resets only after success, retains fields on error and retains the request event ID for an exact retry. Refresh materials now reloads both the material list and available course offerings. An empty offering selector explains the course/assignment prerequisite and disables a new upload.

Isolated tests exercise multipart POST/PUT, exact downloaded bytes and stored SHA-256, course binding, roster/assignment access changes, student/unassigned/anonymous denial, idempotent retry, stale replacement rejection and retained versions. Browser tests cover the file adapter, CSRF/multipart boundary handling, upload feedback/reset, retry, course refresh, student controls, replacement and withdrawal. This implementation validation does not replace the owner's pending material-upload/student-download operational observation.

## Timetable

GET/POST `/api/teaching/timetable/`; PUT `/api/teaching/timetable/{id}/` edits or deactivates. JSON: offering, event_id, title, venue, starts_at, ends_at, active, reason, expected_revision. Assigned authorised staff manage only their courses. End follows start; a confirmed course roster is required. Overlapping time windows compare actual students in approved course rosters. `clash_ids` and a visible warning are returned; saving is allowed. Historical revisions preserve actor, reason, previous snapshot and the overlaps seen at save. Current warning calculations reflect later roster/entry changes. This is dated-entry scheduling; automatic recurring expansion is not inferred.

## Validation

Synthetic isolated Django tests cover recipient scope, detail-only reads, version unread resets/withdrawal, outbox idempotency/unknown/eligibility checks, private retained material access, and student-overlap warning saves. Frontend tests cover linked-message explicit opening, human recipient choices and unknown student exam eligibility. No real notifications or student files are used.

## Create courses before teaching uploads

The HOD **Courses** workspace creates catalogue entries, sessions and semester offerings, then manages teaching-staff assignments. See [course management](course-management.md) for the sequence and existing permission/current-session/roster requirements. Refresh or reopen material/timetable pages after creating an offering. A catalogue course alone is not an available teaching offering.

## Round-up implementation follow-up - 26 October

The message reader now receives focus after an explicit open, displays the recipient's read timestamp, closes back to the inbox and clears old content when the inbox refreshes or another open fails. Listing/highlighting still does not mark a message read. Authors retain receipt counts even when they are also recipients, and the author history displays retained version bodies. These improvements have automated coverage; the owner still needs to confirm the revised experience. Broader visual redesign remains future work.

Announcement notifications are separate from guardian-result emails. Normal startup leaves both workers off. After configuring the private SMTP provider, explicitly start the announcement worker alongside the portal with:

```powershell
.\scripts\start-local.ps1 -TeachingNotifications
```

This processes pending announcement emails. `-EmailWorker` remains the separate guardian-result worker; the two switches may be used together when both queues should be processed. The announcement worker does not require `RESULT_SHARING_ENABLED`, but does require SMTP configuration. Console/dummy/file-only backends cannot mark announcement notifications delivered through the command. Exact request retries preserve versions; unknown or interrupted sending outcomes are not automatically resent.

The local launcher defaults `TEACHING_PORTAL_URL` to its actual frontend port, including alternate ports. An explicit URL is preserved. For recipients using VSCode forwarding, configure that intended reachable portal URL privately before startup; a loopback link reaches only the recipient's own computer. Stop requests finish the current email before shutdown. No live emails were sent during implementation checks.
