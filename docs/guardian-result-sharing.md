# HOD bulk guardian result sharing

8 October 2026. Backend service for email and WhatsApp, using the selected
academic session and semester. Routes are prefixed /api/. Only authenticated,
active staff superusers (HOD) can manage preferences, preview, send, retry or
inspect reports. Session authentication and X-CSRFToken apply to writes.
No adviser/student/guardian account is allowed to trigger this service.
Existing guardians cannot be relinked through Django admin; admin contact edits
use the same student locking convention as the API and delivery worker.

## Report and recipient rules

All guardians with enabled channel preferences and valid contacts are considered;
there is no primary-guardian field. Each delivery contains only that guardian's
student's report. Separate emails are sent, without a shared recipient/CC/BCC list.
Duplicate contacts on the same student/channel are marked duplicate_contact;
one contact shared by guardians of different students receives separate reports.

The report includes student name/identifier, selected session/semester, every
recorded course attempt for that semester with score, saved units and grade point,
semester GPA and cumulative CGPA THROUGH THAT PERIOD. Later semesters are excluded.
Failures and repeated attempts count. Decimal values are not rounded for logic.
The report is a verified-recorded-results summary, not an official transcript or
certification of complete required academic history. No PDF attachment is included.

Any unverified or missing-score result in the selected period or earlier cumulative
history blocks that student's entire report; no unverified rows are silently omitted.
No semester results also blocks that student. Other eligible students may still be
queued after the HOD sees these diagnostics. Students without guardians are visible
in the preview even though they produce no deliveries.

Guardian email must pass validation; phone must be international text of the form
+countrycode... (8..15 digits, starting nonzero). Local phone numbers are flagged,
not guessed or converted. Email/WhatsApp sharing preferences default OFF and are
stored separately from Guardian profile fields. The HOD records the basis of
permission/recipient opt-in or withdrawal; evidence is private, not sent in messages.
A phone number or guardian relationship alone does not establish WhatsApp opt-in.
See the [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/)
for recipient opt-in, honoring opt-outs and approved business-initiated templates.

## HOD workflow / React contract

1. For each guardian, GET/PUT
   students/<student_uuid>/guardians/<guardian_uuid>/result-sharing/:

```json
{"email_enabled":true,"whatsapp_enabled":true,"evidence":"Record the actual sharing permission and recipient opt-in here."}
```

Use false to record withdrawal; retain a meaningful explanation. This records
permission, not an automated determination of consent. Verify the guardian/contact
and appropriate institutional authorization before enabling result sharing.
Ordinary staff guardian-edit permission does not grant control of these preferences.

2. POST result-shares/preview/. The browser generates one request_id UUID and keeps
   it for retries of this same request; there is a maximum of 100 distinct students.
   academic_session is the existing catalog ID, not its display name.

```json
{"request_id":"BROWSER_GENERATED_UUID","student_ids":["STUDENT_UUID"],"academic_session":1,"semester":"harmattan","channels":["email","whatsapp"]}
```

Returns batch id, history_digest, preview reports/recipients/diagnostics, delivery
counts and individual status rows. This saves a draft; it sends NOTHING. Reusing
request_id for the same selection returns the existing batch. Reusing it for a
different selection is rejected. Reports and contact snapshots are persisted for
review/history and should be treated as private academic data.

3. Display reports, recipient addresses/numbers, WhatsApp part counts and skipped
   diagnostics. POST result-shares/<batch_uuid>/send/ when the HOD clicks Send:

```json
{"expected_digest":"COPY_THE_PREVIEW_HISTORY_DIGEST"}
```

A stale digest or changed academic/contact/preference data is rejected: create a
new preview with a NEW request_id and review it. If no eligible recipients remain,
queueing fails. Provider configuration must be ready for every eligible channel;
configuration failure does not partially queue the batch. Otherwise returns 202
and queues only eligible deliveries. Skipped entries remain visible. Repeated
Send clicks on an already queued batch neither create nor resend messages.

4. GET result-shares/<batch_uuid>/ for private preview and delivery status, or
   GET result-shares/ for paginated batch summaries (20 per page). Counts are
   delivery/part counts, not numbers of students or guardians. UI should show
   queued, processing, accepted, failed, unknown, skipped and cancelled separately.
5. POST result-shares/<batch_uuid>/retry/ queues ONLY known failed submissions
   with fewer than three submission attempts. Returns requeued count. Accepted,
   unknown, processing, cancelled and skipped entries are not retried by this API.
   A fresh preview/new batch is a deliberate NEW send and may repeat reports;
   never generate a new request_id as an automatic retry of a Send click.

All report endpoints use no-store caching. Do not put reports or recipient contacts
in analytics, application logs, issue screenshots or browser localStorage.

## Email / WhatsApp provider setup

The adapters use Django EmailMessage and Meta WhatsApp Cloud API. Enable
RESULT_SHARING_ENABLED=true only after provider and worker setup. It defaults false.
Console, dummy and file email backends cannot queue result emails; they must not be
shown as delivered. Configure production SMTP (or a working Django email adapter),
DEFAULT_FROM_EMAIL and credentials as described in .env.example. The test suite
uses Django's in-memory backend and synthetic addresses.

WhatsApp requires a configured Business Platform account, sender phone-number ID,
access token, currently supported explicit Graph API version, approved template
name and language. Supply WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
WHATSAPP_API_VERSION, WHATSAPP_RESULT_TEMPLATE, WHATSAPP_TEMPLATE_LANGUAGE through
private process settings; never commit the token. This does not automate WhatsApp
Web or require a guardian login account. Validate the chosen Graph version and
approved template in your provider sandbox before enabling actual deliveries.

The approved template must have EXACTLY ONE body text parameter. A possible
wording to submit for review is: "Your reviewed student result report: {{1}}.
For questions please contact the department." Provider approval/classification
is external; this service does not claim that this wording has been approved.
The implementation follows the official
[template payload structure](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/template/).

WhatsApp body parameter text is flattened to one line. Long reports are split
into numbered parts, each below 1024 characters, and stored as separate deliveries
with part_number. No course information is discarded. The HOD previews the number
of parts, each of which is a separate provider submission and may incur costs.
If only one part fails, retry sends only that part. Email contains the complete
report in a single plain-text message. Template approval and an actual Meta sandbox
submission remain required to establish real provider compatibility.

## Worker / reliability

The HTTP send operation does not make network calls or hold the browser open
while sending every message. A worker submits queued messages:

```powershell
.\.venv\Scripts\python.exe manage.py process_result_shares --limit 100
```

Run it regularly under a supervised deployment worker/scheduler using the same
PostgreSQL database and provider configuration as the API. The command exits after
at most the specified count; it is not a permanently running daemon. No scheduler
or production service has been installed in this workspace. Use PostgreSQL for
production queue workers; the SQLite test suite does not validate real concurrent
worker/database-lock behavior. Worker submission timeout is 20 seconds per provider
call. It claims a queued row conditionally before submitting and uses student/delivery
locks while rechecking reviewed data and submitting; academic/contact API changes
can wait briefly on those locks.

Before EVERY submission, the worker rechecks current results, guardian details
and preference snapshot. Any change cancels pending deliveries for that student;
create a fresh reviewed batch as appropriate. Opt-out therefore blocks pending
submissions when recorded before the final preflight; already submitted messages
cannot be recalled. Direct SQL/maintenance writes bypass the API lock conventions.

accepted means email server/Meta ACCEPTED the submission, not delivered/read.
Meta message ID is retained when returned. Delivery/read/bounce webhooks are NOT
implemented. Definite provider rejections become failed; connection/timeouts,
server errors or ambiguous responses become unknown and are NOT automatically
retried because the message might already have been accepted. A worker crash can
leave processing rows; do not automatically reset them to queued. An operator must
reconcile provider records first. Exactly-once external delivery is not promised.

Diagnostic codes contain stable explanations, not raw provider exceptions,
response bodies, recipient addresses or access tokens. Review failed and unknown
rows through HOD-only status endpoints. Configure retention and backup protection
for batch snapshots/contact data before using live institutional records.

## Schema / validation / remaining integration

academics migration 0005 adds GuardianSharingPreference, ResultShareBatch and
ResultShareDelivery with uniqueness on batch/guardian/channel/part_number. It was
applied only in isolated tests; development/shared database is unchanged. Include
this migration and the preceding academic migrations when preparing PostgreSQL.

Tests use synthetic contacts, locmem email and mocked WhatsApp HTTP submissions;
no real guardian received a message. Covered cases include HOD/CSRF restrictions,
recipient isolation, GPA/CGPA and repeated failures, historical verification,
missing contacts/preferences, duplicate contacts, stale previews, withdrawal,
queue idempotency, known failures/retry limits, uncertain outcomes, multipart
reports, template payload and provider error classification.

React controls, production scheduling, approved WhatsApp template/token, SMTP,
real PostgreSQL concurrency tests, provider sandbox acceptance, consent/contact
review and live delivery validation remain deployment/integration tasks.

Final local validation: all 236 backend tests passed on isolated SQLite, Django
system checks passed and no migration drift was detected. Provider calls were
mocked/in-memory; PostgreSQL and live provider acceptance remain untested here.
