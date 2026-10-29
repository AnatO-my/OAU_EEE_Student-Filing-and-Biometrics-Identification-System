# Attendance and teaching rehearsal — staged for 26 October 2026

**Status: NOT RUN.** This pack is prepared for later operator evaluation. Writing these instructions and checking launcher syntax did not run migrations, seed accounts, import attendance, send mail or operate a scanner. Previous automated regression passes are separate evidence, not these Chapter 4 observations.

Use the [master pack](../README.md) and its run/evidence forms. The case schema in `results-template.csv` matches the master case-results template. All expected results below are hypotheses to check; leave actual results blank until observed.

## Shared isolated environment

From the repository root, later in the controlled session:

```powershell
$evalRoot = Join-Path (Get-Location) 'private-data\evaluation\2026-10-26\run-01'
.\.venv\Scripts\python.exe scripts/evaluation_stage.py init --root $evalRoot
.\.venv\Scripts\python.exe scripts/evaluation_stage.py prepare --root $evalRoot
.\.venv\Scripts\python.exe scripts/evaluation_stage.py serve --root $evalRoot
```

`init` requires a NEW directory and writes only its scratch marker/folders and a private random session key (never include that key in evidence). `prepare` prompts twice for a strong synthetic password, refuses any existing database and applies migrations ONLY to the new guarded `scratch.sqlite3`. It does not migrate the user's normal database. No password is printed or stored. A partial failed preparation must be kept for diagnosis; initialize a different new run directory, rather than delete/overwrite it.

The normal website launcher, normal `manage.py migrate`, development database, real mail settings and real biometric files are outside this session. If `DJANGO_SETTINGS_MODULE` is already set to normal/production settings, the harness refuses; explicitly clear that shell variable before using the scratch launcher. The separate `config.evaluation_settings` fixes SQLite/private-media/locmem, blanks external WhatsApp credentials, disables result dispatch, pins setup/reset links to the scratch frontend, forces the local placeholder OCR backend and uses separate session/CSRF cookies. Scratch artifacts are ignored under `private-data/`, not committed.

Start the frontend in a second terminal, still pointing only to this scratch backend:

```powershell
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8876'
Set-Location frontend/portal
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Use `http://127.0.0.1:5175/portal`. Never run this proxy against the normal application while calling it an isolated test. Read `run-manifest.json` first and confirm backend URL/SQLite/private-media paths. If either port is occupied, stop and diagnose; do not silently use the existing service.

The manifest supplies actual account IDs, student UUIDs, course-offering IDs, meeting IDs and fixture paths. Use handles, not guessed numeric IDs:

- EVAL-HOD: departmental oversight. EVAL-HOD-SUCCESSOR: ordinary staff for the separate ownership-transfer scenario.
- EVAL-ADVISER: current-level adviser and assigned course staff. EVAL-LECTURER: assigned course staff. EVAL-UNASSIGNED: matching capabilities without course/adviser assignment, for negative checks.
- EVAL-STUDENT-A and EVAL-STUDENT-B: actual usernames `EVAL/001` and `EVAL/002`; synthetic shared course-roster students.
- EVAL-SETUP: username `EVAL/003`, mandatory password change enabled; NOT initially on the shared attendance rosters. Use this record for the late-registration exception after its separate setup journey.

For a non-roster student boundary check, complete EVAL-SETUP's mandatory password-change journey first. A rejection caused by the setup gate is not evidence that course-membership enforcement was tested. Keep SETUP outside the teaching rosters until ATT14.

All accounts initially use the operator-chosen synthetic password. Do not record it in results, screenshots, terminal transcripts or run manifests. Use separate browser profiles/private sessions for each role; do not rely only on changing a menu label.

`offerings.teaching.EEE901` and `.EEE902` have the same two approved students; `meetings.IMPORT` belongs to EEE901, `meetings.WRONG_TARGET` to EEE902. Their initial recording windows last 12 hours from preparation. After expiry, use a new isolated run or deliberately create a new meeting and regenerate matching fixtures; do not change the clock or silently edit source evidence.

The shared seed also supplies the root pack's synthetic prior/current GPA catalog and VERIFIED prior results only. It does NOT import current result CSVs, fabricate GPA outcomes or set attendance/exam decisions in advance. These are synthetic grading assumptions, not institutional repeat-course policy.

### Optional private cross-device forwarding

Default access is local-PC only. For a private authenticated VS Code frontend forwarding URL, supply its EXACT HTTPS origin (no path, query, credentials or wildcard):

```powershell
.\.venv\Scripts\python.exe scripts/evaluation_stage.py serve --root $evalRoot --frontend-origin 'https://EXACT-FRONTEND-HOST'
```

This changes only scratch `ALLOWED_HOSTS`/CSRF/portal-link settings, retaining the loopback backend bind. In the frontend terminal set `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS` to that exact hostname and keep the API proxy at `http://127.0.0.1:8876`. Follow the master pack for private forwarding/login steps. No tunnel was opened while staging. If the actual forwarding URL is unknown, host/CSRF/phone access is BLOCKED, not passed. Never use `*`, public unauthenticated forwarding or broad CORS changes.

## Synthetic fixtures versus physical scanner evidence

`fixtures.pending-valid.jsonl` is a sealed JSONL file bound to `meetings.IMPORT`; its opaque bytes literally identify themselves as **SYNTHETIC ONLY, NOT A FINGERPRINT**. The replay file is byte-identical. The append file adds a second synthetic capture to the same batch; the conflict file changes the existing first event while keeping its UUID. On the wire, uptime_ms is a JSON INTEGER (the database stores its decimal text separately); a string would fail format validation before reaching the intended immutable-event conflict. These exercise storage, binding, integrity and review—not fingerprint recognition accuracy.

Never report synthetic import/review as a successful biometric match. The explicit resolution step is a staff decision with identity/timing evidence, not an AS608 algorithm result. Device boot elapsed milliseconds are not trusted absolute capture time.

Physical receive/download/matching runs belong to the separate hardware protocol and private device-run logs. Keep the original physical file unchanged. A real file must already be bound to the intended scratch meeting; do not edit its meeting UUID or contents to make a rejected import pass. Link its device_run_id and original file hash separately, and label the input source REAL_DEVICE rather than SYNTHETIC. Preserve actual board/firmware/scanner/clock facts and operator failures; do not invent recognition labels.

## Attendance/import/exam cases

Use the master session order: run MSG/MAT/TT on the initial A/B rosters BEFORE starting the ATT sequence. Then run ATT01–ATT15 in order. ATT14 deliberately adds SETUP and changes later recipient expectations. HOD ownership transfer belongs last in the separate master workflow. Record each actual outcome before changing state; use the assigned lecturer unless stated otherwise. Do not reset earlier observations or silently remove SETUP to recreate a two-recipient expectation. Use a new scratch run if the initial fixture state is needed again.

| Case | Action | Expected check and evidence |
|---|---|---|
| ATT01 | Open Attendance as assigned lecturer, unassigned staff, student A and HOD in separate sessions. | Lecturer sees own two courses/meetings; unassigned staff cannot inspect them; student sees only own history/eligibility; HOD can inspect department fixtures. Record role and visible titles, no password. |
| ATT02 | Select IMPORT meeting, preview pending-valid.jsonl. | Preview shows one new capture, correct meeting/digest and pending identity/timing. No batch/attendance record is committed by preview. Time click Preview → summary visible. |
| ATT03 | Confirm/import the same unchanged file. | One durable batch/event/receipt, retained evidence, no automatic presence or absence. Save sanitized response metadata and attendance table. Time click Import → receipt visible. |
| ATT04 | Preview/import pending-valid-replay.jsonl. | Exact replay: same receipt/event, replay flag, no duplicate attendance. Record counts before/after, response time. |
| ATT05 | After ATT03, preview/import pending-conflict.jsonl. | Existing immutable event differs: conflict/HTTP 409, no partial new event or presence. Before ATT03 this file is merely new evidence; that is NOT the conflict test. |
| ATT06 | Select WRONG_TARGET meeting and preview valid IMPORT file. | HTTP 400/wrong meeting; original target remains fixed and no target-B batch is created. |
| ATT07 | In IMPORT recording window, manually record student A with reason “Synthetic ongoing fingerprint inability”. | Presence saved without biometric reference; duplicate distinct scan/manual events never create two student/meeting records. This tests manual fallback, not recognition. |
| ATT08 | In retained captures, explicitly choose deferred capture for review; select historical student A, written synthetic identity reason and timing confirmation. | Archived event preserved, reviewed resolution audit links A; still only one presence. Deliberately trying an outsider/unconfirmed timing is rejected. Live flagged context can be checked on a separate unselected capture; no real live transport is inferred. |
| ATT09 | Set discretionary 75% threshold with written test reason; close collection without finalising. | Exam basis remains finalised-only: zero eligible finalised denominator means UNKNOWN, not eligible/restricted. Closing alone does not imply review. 75% is a test choice, not departmental policy. |
| ATT10 | Refresh review evidence, inspect records/excuses/archive, confirm reviewed and finalise with reason. | Closed meeting finalisation revision recorded; A=100%/eligible and B=0%/restricted, based only on this finalised meeting. Archives intact. Save role/table/revision. |
| ATT11 | Grant B a normal written formal excuse, then an explicit exam exception; later revoke both with reasons. | Excuse excludes numerator/denominator: B rate UNKNOWN with zero denominator. Approved exception is separately labelled exception_approved. Revocation restores underlying calculation without deleting audits. Record intermediate states. |
| ATT12 | Import pending-append.jsonl after finalisation. | New event retained, old source approval stale, meeting removed from exam denominator until explicitly re-reviewed; no fabricated automatic match. A/B exam decisions become UNKNOWN unless an independently active exception exists. |
| ATT13 | Re-review and finalise current evidence leaving second unknown archived; retry exact accepted valid file. | Finalisation revision increases; rates use confirmed records and retained unknown capture. Exact old accepted-file retry does not create evidence or stale review. |
| ATT14 | HOD adds SETUP student to current EEE901 roster, then opens a future meeting. Lecturer explicitly records retrospective excuse for SETUP against old IMPORT meeting. | Old student_ids remain A/B; future meeting includes SETUP. Explicit retrospective flag/current-approved roster required. Separate retrospective count, no historical presence/absence/denominator. Arbitrary outsider fails. |
| ATT15 | Authorised adviser/lecturer links a SYNTHETIC scanner UUID/reference to A, then replaces that mapping; check unassigned/peer access. | Old reference disabled with history, new link preserves student UUID/matric; no physical enrolment is claimed. Unauthorised/out-of-scope changes rejected. Do not overwrite a real scanner slot. |

Browser labels may show validation messages instead of numeric HTTP status. Use Network response metadata for exact status; do not record raw authentication cookies/CSRF tokens or put biometric bytes in the public report.

## Messages, materials and timetable

| Case | Action | Expected check and evidence |
|---|---|---|
| MSG01 | Lecturer publishes student message filtered to EEE901. | On the initial roster (BEFORE ATT14), the snapshot contains A/B; no approval queue. Sender sees 0/2 reads. After ATT14 the course includes SETUP too, so that is a different starting state requiring a documented expectation or fresh run. Other staff/peer users outside audience cannot read the body. |
| MSG02 | A opens list only, then deliberately opens the message; B leaves unopened. | Listing/email-link highlighting does not mark read; detail opening changes only A's latest-version receipt. Sender sees 1/2. |
| MSG03 | Author edits to a new version; A/B inspect current version. | New receipts initially unread; old version's A read timestamp preserved. Record both version/read counts. |
| MSG04 | Author withdraws with confirmation. | Current body redacted/withdrawal notice, prior author audit retained. Short link-only notices queue for prior recipients; old body is not exposed to recipients. |
| MSG05 | Later use guarded capture-notifications below on a fresh pending current message; open its highlighted link without Open, then deliberately Open. | Only locmem acceptance/preview is measured; no SMTP delivery claim. Generic mail excludes body/private documents. Previewing email does not mark website read. Exact command rerun does not resend processed rows. |
| MAT01 | Lecturer uploads material-v1.txt to EEE901; A downloads; unassigned staff/nonroster user attempts download. | Current roster authorised, unrelated users rejected; private attachment, no public file URL. Time Submit → saved version and click Download → browser save prompt/bytes received separately. |
| MAT02 | Lecturer replaces with material-v2.txt. | Version increments; assigned staff can inspect archived v1, student only current v2. Preserve both byte hashes/version metadata as evidence. |
| MAT03 | Lecturer withdraws with written reason and confirmation. | Latest is withdrawn, student cannot download older versions to bypass withdrawal; assigned staff archive retained. |
| TT01 | Lecturer creates dated EEE901 entry, then overlapping EEE902 entry with same approved students. | Both save; visible student-overlap warning, not a blocking error. Record both course labels/times/warnings. |
| TT02 | Edit time to remove overlap, then withdraw/deactivate an entry. | Current warnings update, revisions retain earlier overlap facts; inactive entries disappear from student timetable. |
| TT03 | Student A, unassigned staff and HOD inspect timetable; unassigned staff tries editing EEE901. | Enrolled student sees own courses, unassigned scope cannot modify them, HOD departmental oversight. Same level alone is not an overlap rule: actual shared roster students determine warning. |

## Controlled notification previews — later only

The browser/backend process uses locmem email; a normal separate mail-worker process cannot expose its in-memory mailbox to the browser. No public mailbox endpoint is added. Account setup/reset email content is checked by separate isolated automated tests; this command captures only generic teaching notices.

After creating pending current teaching messages in the scratch browser, later run:

```powershell
.\.venv\Scripts\python.exe scripts/evaluation_stage.py capture-notifications --root $evalRoot
```

The command revalidates scratch paths/locmem, refuses non-example.invalid destinations and reuses the existing notification worker in-process. It writes a uniquely named private `evidence/teaching-notifications-*.json` with generic message bodies, accepted/skipped/unknown states and per-send elapsed_ms. It may change outbox rows in this scratch database only. These are **locmem captures, not real SMTP delivery or recipient reading**. Real SMTP transport must remain NOT_RUN unless a separately authorised test occurs. Do not copy account-reset/setup secrets into this evidence.

## Observation and timing discipline

For each case copy a result row, set run_id/repetition/role/input and preserve expected. Record actual UI state/status/counts; choose PASS/FAIL/PARTIAL/BLOCKED only after observation. Evidence paths must point to actual screenshots/sanitized responses/private outputs, never invented filenames. Capture a distinct device_run_id only for real hardware evidence.

Use consistent timing boundaries: action click/request start → corresponding visible completed response. Record backend Network response duration separately from browser journey timing; do not average them together. Suggested performance pilot: three controlled repetitions of preview, exact replay and read-only refresh, recording payload size/device/browser/network. Do not repeatedly submit state-changing actions under new UUIDs just to get faster timings. These few cases are not population recognition or production load evidence.

Stop on unexpected role access, new conflicting source state, uncertain write or insufficient evidence. Preserve failures and scratch directories; do not overwrite prior observations to force expected outcomes. Live schema/application migrations stay deferred until the agreed Chapter 4/deployment stage.

## Staging self-check

Only this bounded command was authorised while preparing the pack:

```powershell
.\.venv\Scripts\python.exe scripts/evaluation_stage.py self-check
```

It parses launcher/settings syntax, checks exact-origin rejection, and validates baseline/append/format-valid changed-event JSONL variants entirely in memory using the stdlib-only parser and existing pure fixture helper definitions. It does not import Django test models, initialise Django or run a seed, migration, importer, server, email, scanner or operator case. In particular, format validity is not proof of the later HTTP 409 outcome. Actual seed/service/browser execution remains NOT_RUN.
