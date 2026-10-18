# Pending capture batch API - 16 October 2026

Implemented locally: authorized USB JSONL preview/import, immutable capture
evidence, append-only batches and durable receipts. Import never marks a student
present or absent. Matching, timing review, reconciliation and device
authentication remain pending.

## Routes and access

For a backend-created class-session UUID:

| Method | Route | Result |
| --- | --- | --- |
| POST | `/api/attendance/sessions/{uuid}/pending-batches/preview/` | Validate complete file and conflicts without writes |
| POST | `/api/attendance/sessions/{uuid}/pending-batches/` | Commit pending evidence and return a receipt |
| GET | `/api/attendance/sessions/{uuid}/pending-batches/` | Paginated batch metadata and counts |

POST original file bytes with `Content-Type: application/x-ndjson`. Multipart
uploads and JSON wrappers are unsupported. Import requires `X-Capture-SHA256`
with the **whole-file** `file_sha256` returned by preview, distinct from the
trailer's digest of the preceding JSONL bytes. Preview does not reserve a batch
or grant later access; import revalidates the file and authorization.

Both POST routes use existing session authentication and CSRF protection.
Ordinary staff need an active course assignment, `attendance.view_attendance`
and the separately granted `attendance.import_pending_captures` permission in
the current academic session. The active HOD can also review historical classes.
Manual recording/profile-export permissions alone do not grant ingestion.
Revoked staff cannot regain access through retries. Closed or expired classes
accept evidence for later timing/identity review.

## Upload example

For a local prototype with an authenticated PowerShell web session and CSRF token:

```powershell
# Set apiBase, classSession, batchFile, webSession and csrfToken from your session.
$pendingUrl = "$apiBase/api/attendance/sessions/$classSession/pending-batches/"
$captureHeaders = @{ 'X-CSRFToken' = $csrfToken }
$preview = Invoke-RestMethod -Method Post -Uri ($pendingUrl + 'preview/') `
  -WebSession $webSession -Headers $captureHeaders `
  -ContentType 'application/x-ndjson' -InFile $batchFile
# Review metadata, counts and recovery/timing flags before importing this file.
$captureHeaders['X-Capture-SHA256'] = $preview.file_sha256
$receipt = Invoke-RestMethod -Method Post -Uri $pendingUrl `
  -WebSession $webSession -Headers $captureHeaders `
  -ContentType 'application/x-ndjson' -InFile $batchFile
```

This sends file bytes without printing biometrics. The preview hash binds the
selected bytes; it is not proof that a person inspected the preview.

## Validation and retry rules

The independent backend parser accepts the v1 downloader schema with limits of
2 MiB per file, 512 events, 4096 bytes per line and 2048 decoded bytes per probe.
The raw request stream is read with an explicit bound before decoding. It rejects
missing/unknown/duplicate fields, unsupported versions, non-finite JSON,
noncanonical or zero UUIDs, invalid source/clock metadata, noncanonical Base64,
duplicate event UUIDs, backwards elapsed time within a boot, truncation and
incorrect counts or trailer SHA-256. Student IDs, matric identifiers and scanner
slots are unsupported capture fields.

The class UUID must match the URL and an existing class in the caller's scope.
A batch UUID is permanently bound to its class and commissioning metadata.
Events retain their UUID, order, boot UUID, exact uint64 uptime and probe bytes.
Uptime uses decimal text in storage to preserve all bits on SQLite/PostgreSQL;
it is never converted into a calendar timestamp.

New snapshots may append to the exact stored prefix. Older prefix snapshots
remain safe to retry. Changed events/order/metadata or event UUID reuse across
batches return HTTP 409 and reject the whole import. Manual event UUID collisions
are rejected in both directions. Invalid files return 400; unsupported content
types return 415. Rejected imports leave no batch, event or receipt rows.

## Receipts and pending evidence

A new accepted file snapshot returns 201 with `receipt_id`, `file_sha256`,
`received_at`, incoming `event_count`, `new_events`, `existing_events` and total
`batch_event_count`. An exact file retry returns 200, `replayed=true` and its
original receipt, preserving first importer/time. A different serialization of
the same events can receive a new file receipt with zero new events. Receipts
commit atomically with the evidence; retrying a lost response recovers the receipt.

Receipt time is server time. `captured_at` remains null; boot UUID and elapsed
milliseconds are retained. All batches return `state=pending_review`, identity
and timing review required, and `device_authenticated=false`. Empty batches
remain pending and do not complete a class. Every receipt retains its interrupted
write flag; once observed, batch `recovery_review_required` stays true. This does
not recover an unfinished device file. Receipts require device files to be
retained and never authorize deletion.

No response/error/list includes probe bytes/Base64. No raw-probe read/export API
or Django admin screen is registered. Probe storage is application-restricted
database binary data; encryption/key management, retention/deletion policy and
deployment hardening remain pending. Labels and hashes do not authenticate
hardware. The earlier physical test batch has a synthetic class UUID and must
not be rebound to a real class. Unreviewed evidence creates no attendance records,
absences or warnings.

## Verification and next work

Migration `attendance/0003` is generated and tested only in isolated databases.
Do not apply it to shared/development databases before schema reconciliation.
Synthetic tests cover parser limits, downloader interoperability, permissions,
CSRF, course scope/cutover/revocation, retries/appends, uint64 preservation,
rollback, recovery flags, metadata privacy and absence of attendance writes.
PostgreSQL contention and real loopback HTTP uploads, CSRF, interrupted requests
and application-process restart are now validated. See
[attendance-validation.md](attendance-validation.md) for the 337-test result and
isolated rerun command. React browser interaction and field operation remain pending.

Next implement restricted enrollment-to-student bindings and reviewed
scanner-assisted identity resolution, then reconcile through attendance services.
Trusted clocks, completed-class metrics, cancelled/excused states, 75% warnings,
React integration and authenticated devices remain separate work.
