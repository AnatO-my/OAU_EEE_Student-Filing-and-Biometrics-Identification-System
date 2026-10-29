# Chapter Four evaluation pack - 26 October 2026

**STAGED / NOT RUN.** This pack prepares the later operator session. It does not assert document, course, account, hardware or full-semester outcomes. Previous regression evidence (583 isolated backend tests with 29 skips; 143 portal and 14 guardian UI tests; both builds) remains a separate checkpoint. No reminder or automatic session has been scheduled.

## Scope and evidence split

Read the current [Chapter Four](../../report-review/report-prototype/chapter_4.tex) and [decision register](../../report-decisions.md). The missing owner journeys are student-document upload/retrieval/replacement review, teaching materials, timetable, accepted HOD transfer, full-semester GPA/CGPA and actual attendance import/integration. The study also needs clearly bounded timing and cross-device observations. Hardware assembly/power measurements and any equivalent manual filing baseline remain optional manual evidence only if the apparatus and a fair procedure are available.

- [Student documents, accounts and calculation checklist](student-workflows.md) and its independent synthetic GPA fixture are owned by that subpack.
- [Attendance, messaging, materials and timetable checklist](teaching-attendance/README.md) supplies synthetic pending-capture fixtures and exact service/browser cases.
- [Scanner/transfer timing session](../../../hardware/fingerprint-diagnostic/TIMING-SESSION.md) reuses the existing physical CLI with monotonic wrappers. It is not an automated recognition or web-to-scanner bridge.
- [Existing biometric evaluation reference](../../fingerprint-score-and-evaluation-reference.md) and [recorded pilot procedure](../../fingerprint-reporting-test-session.md) define recognition outcomes and logging boundaries.

Exact guarded launcher commands and supplied fixture paths are below. A missing prerequisite is **BLOCKED**, never PASS.

## Common roles and private run directory

Only generated synthetic accounts/data belong in the software session. Shared roles are `EVAL-HOD`, `EVAL-HOD-SUCCESSOR`, scoped adviser/course staff, `EVAL-UNASSIGNED` and `EVAL-STUDENT-A/B`; the generated `run-manifest.json` supplies actual account identifiers, student/course/meeting IDs and fixture paths. A role handle is a label, not necessarily its username: `EVAL-STUDENT-A/B` sign in as `EVAL/001` and `EVAL/002`, and `EVAL-SETUP` as `EVAL/003`, as declared by that manifest. Roles may be combined only where the seed manifest explicitly says so. Addresses use reserved non-deliverable example domains and the backend must use isolated-memory email. Never guess IDs or replace the normal application database with evaluation data.

Actual outputs belong under ignored `private-data/evaluation/2026-10-26/<run-id>/` (or the launcher's explicitly verified scratch directory). The launcher prompts for a strong synthetic password and does not log or store it. Do not put it in tracked templates, result sheets or screenshots. The generated role map contains no password. The launcher must initialise only a disposable scratch schema when the operator deliberately runs it later. Do not run the normal project migration/server command against current settings as a substitute. No production migration, provider email, physical capture, scanner gallery rewrite or public tunnel is part of staging.

## Operator sequence for later today

1. **Freeze the run metadata.** Choose a new run-folder name but do not create/copy into it before `init`, which refuses an existing directory. After initialisation, copy the templates as shown below, then record actual date/time/timezone, operator, app/firmware revision and dirty-worktree status. Keep the launcher-generated `run-manifest.json` unchanged; fill the separate `operator-session.json` copy for observations. Predetermine case/repetition counts. Record unavailable fields as unknown. The existing 31-person aggregate account is not a source of new scan-level rows.
2. **Initialise the safe scratch workspace using the linked launcher.** Check the printed database path, private file root and locmem email backend before accepting the run. Use the generated fixture manifest and the synthetic password you chose. Scratch schema creation is distinct from the deferred live migrations. Keep one untouched seed or create a fresh run for destructive-to-fixture transitions such as HOD acceptance or student archival.
3. **PC baseline and roles.** Start the scratch backend and portal using the launcher's exact commands. Log in as each generated role. Verify the mandatory-password gate where applicable, permitted student/course scope and rejection for the unassigned account. Record the actual account used for each case, without storing its password in the result row.
4. **Student documents/accounts/calculations.** Follow the student subpack. Exercise initial upload, candidate replacement with old active content, reject/resubmit/approve, active/archive download and unrelated-user denial. Run contact proposals and non-disruptive gate checks in the subpack order, but defer matric/identity correction, HOD acceptance and archival to terminal step 9 (or a fresh scratch run). A locmem-backed automated credential/reset check is not a manually received email journey. Compare semester/cumulative results to the independent declared fixture, retaining units, grades, attempts and as-of-period rules. A synthetic example validates only those inputs, not institutional policy or all possible academic histories.
5. **Messages, materials and timetable.** Follow the teaching subpack, running MSG/MAT/TT cases before ATT14 adds SETUP to the roster; otherwise MSG01's two-recipient expectation no longer describes the same fixture. Verify actual website-open reads, revision unread state/history, withdrawal notice and link-only locmem notifications. Check retained material versions/private scope and a deliberate common-student timetable clash that warns while saving. Capture both expected success and intended rejection states.
6. **Synthetic attendance path.** Use the generated probe-byte fixture for preview/import/replay/conflict, review/finalisation, excuse and rate/threshold/exception checks. It is not a real fingerprint match. Verify ordinary provisional rates separately from finalised-only examination eligibility. Unset/empty evidence remains unknown. Preserve unresolved captures and historical rosters; retrospective excuses do not backfill presence.
7. **Physical attendance/timing only if ready.** Use the hardware checklist, a known fixed gallery and an existing prepared meeting-bound batch. Collect real evidence only when the operator intentionally starts that separate step. No-match, capture/transport failure and unresolved identity are separate outcomes. A successful download or pending import alone is not confirmed student attendance. No trusted live web-to-scanner bridge is supplied by the metadata UI.
8. **Device/browser repetitions.** Repeat selected read/upload/message/course journeys on available PC, Android and iPhone browsers, using the same logical case/role and separate repetition rows. Record browser/OS versions, viewport, dev/production build and **local vs VS Code forwarded** connection mode/URL. For state-changing repetitions, use a fresh scratch run with the same declared initial fixture; repeated initial upload and replacement approval are different starting states and must not be pooled. A borrowed screenshot is not a device run. If a device/connection is unavailable mark BLOCKED/SKIPPED with a reason, and do not generalise another browser's result to it.
9. **Terminal fixture-changing cases.** Only after GPA imports, teaching/attendance and chosen device repetitions, run identity/matric correction, HOD acceptance and student archival (or run them in a separate fresh scratch run). Matric correction changes the identifier used by the supplied GPA CSVs; HOD transfer changes authority, and archival disables student access. Do not carry those altered fixture assumptions into earlier cases.
10. **Review evidence and finish.** Check the resulting state as well as the HTTP/browser response. Keep raw failures and abandoned attempts. Fill actual outcome/status and evidence paths only after observation. Sanitize screenshots/log excerpts before report use. Summarise actual counts and comparable repeated timings; do not replace unrun rows with a regression-test pass.

## Measurement boundaries

Each result row names its start/end events. Use a single monotonic clock for a measured interval; UTC/timezone timestamps label the run, not cross-clock duration. Keep user-task time (e.g. selecting upload through confirmed publication), authenticated HTTP time (request send through completed response) and scanner phase timings separate. Record UI waits, file size, gallery/batch count, network path and whether a repeat uses the same saved bytes or a fresh placement.

For repetitions retain every duration/failure, completed/planned counts and the protocol's exclusion reasons. Median and min/max are useful descriptive summaries of comparable repeats. Do not pool devices, empty/populated batches, different byte counts/settings or genuine/unenrolled modes. Timeouts are not measured latency; repeated saved-probe comparisons are not independent people or new placements. Raw matching score is unitless, not a probability.

## Forms and status rules

| File | Use |
| --- | --- |
| [run-manifest-template.json](run-manifest-template.json) | App/fixture/device/hardware provenance and planned repetitions. Copy privately and fill before running. |
| [case-results-template.csv](case-results-template.csv) | Case ID, role, input, expected/actual, status, timing boundaries and evidence. One row per repetition. |
| [evidence-index-template.csv](evidence-index-template.csv) | Private raw artifact path, type, source case, integrity hash and sanitised report derivative. |
| [device-runs-template.csv](device-runs-template.csv) | PC/Android/iPhone browser/OS, connection mode, build, repeated case outcomes. |
| [extraction-field-check-template.csv](extraction-field-check-template.csv) | Prospective manual source-versus-output comparison with actual field denominator/provenance. |
| [physical-measurements-template.csv](physical-measurements-template.csv) | Optional actual circuit/power/enclosure observations with instrument/method. Blank is not a measurement. |

`NOT_RUN` is the default. `PASS` requires observed expected behaviour and retained evidence; `FAIL` is an observed mismatch. `PARTIAL` means some required observation is missing. `BLOCKED` records a missing prerequisite; `SKIPPED` records an explicit decision not to run; `CANCELLED` records an interrupted attempt. Do not silently discard FAIL/CANCELLED repetitions or call unsupported stages successful.

For the 128-record source document, do not invent a golden CSV, checked-field count or log for the old claim. If the owner repeats it with authorised private input, create a **new** ledger from actual source cells/page/table/row references, compare every stated field and record all mismatches. Keep source-reported averages separate from calculated ones, `F` distinct from `NG`, and missing values distinct from zero. One standard-layout sheet cannot establish accuracy on arbitrary future PDFs; image-only PDFs still require external OCR first.

## Chapter Four handoff after the actual run

Export a sanitised case summary, observed-versus-expected table, counts/denominators and timing table with phase names. Cite private run IDs rather than raw fingerprints, credentials or personal records. Preserve the earlier logged pilot, the additional operator-reported aggregate exercise and these new prospective observations as separate datasets. Record remaining failures/limitations and missing apparatus honestly. Update the report only after this review; this staging pack itself is not a result.

## Supplied fixture index

Use [student-case-results.csv](student-case-results.csv) for its 23 cases and [teaching-attendance/results-template.csv](teaching-attendance/results-template.csv) for its 26 cases: 49 planned rows, all NOT_RUN with blank actual outcomes. The master case template is header-only for additional declared observations. These contain expected behaviour, not observed results. Reuse the same master-generated run for the linked subpacks unless intentionally starting a separately recorded fresh run; their repeated launcher examples are not a request to initialise a second hidden environment.

- [Document v1](fixtures/synthetic-student-document-v1.pdf), [document v2](fixtures/synthetic-student-document-v2.pdf) and [fixture integrity index](fixtures/document-fixture-integrity.csv): visibly synthetic, pre-rendered files. Use these without regenerating. The optional generator `scripts/evaluation_document_fixture.py --output-dir <FRESH-folder>` refuses overwrite and is only for deliberate later reproduction.
- [Current semester CSV](fixtures/results-semester.csv), [B repeat attempt](fixtures/results-repeat-b.csv), [A score correction](fixtures/results-score-correction-a.csv).
- [Manual calculation ledger](fixtures/gpa-manual-ledger.csv) and [independent expected values](fixtures/gpa-independent-expected.csv). Under the declared synthetic scale/all-attempt rule, baseline A/B GPA/CGPA is 3.36/3.16; B after repeat is 3.71/3.41; A after verified correction is 3.82/3.42. Exact fractions/inputs are retained. These are expected fixture values, **not** observed application results or approved institutional policy.
- The launcher generates meeting-bound `pending-valid.jsonl`, exact replay, append and conflicting variants plus two text course-material versions inside the private run's `fixtures/`. Its probes are explicit synthetic bytes, not real fingerprints.

## Exact launcher commands - run later, not part of staging

Prerequisites: use the repository's already configured `.venv` and portal dependencies. Close any unrelated process occupying evaluation ports; do not redirect the scratch frontend to the normal backend. `self-check` is the only setup-free harness check; it does not prepare data or perform an operator case.

PowerShell terminal 1, repository root:

```powershell
Set-Location -LiteralPath 'C:\Users\Ot\Downloads\EEE-Project'
$evalPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
$evalRun = Join-Path (Get-Location) 'private-data\evaluation\2026-10-26\run-001'
& $evalPython scripts/evaluation_stage.py self-check
# Choose a different fresh run name if run-001 already exists; never delete/reuse evidence.
& $evalPython scripts/evaluation_stage.py init --root $evalRun
& $evalPython scripts/evaluation_stage.py prepare --root $evalRun
```

`init` creates only a sentinel and empty private directories. `prepare` is the later explicit operation that creates/migrates **only a new guarded scratch.sqlite3** and seeds invented data. It refuses an existing database/run manifest, wrong settings, unsafe paths and non-locmem persistence/transport. If `DJANGO_SETTINGS_MODULE` is already set to normal settings, open a fresh terminal without that setting; do not point the launcher at the normal database.

After successful preparation, copy operator forms, without overwriting the generated fixture manifest:

```powershell
$evalPack = Join-Path (Get-Location) 'docs\evaluation\2026-10-26'
$evalForms = [ordered]@{
 'run-manifest-template.json' = 'operator-session.json'
 'case-results-template.csv' = 'case-results.csv'
 'student-case-results.csv' = 'student-case-results.csv'
 'teaching-attendance/results-template.csv' = 'teaching-attendance-results.csv'
 'evidence-index-template.csv' = 'evidence-index.csv'
 'device-runs-template.csv' = 'device-runs.csv'
 'extraction-field-check-template.csv' = 'extraction-field-check.csv'
 'physical-measurements-template.csv' = 'physical-measurements.csv'
}
foreach ($evalForm in $evalForms.GetEnumerator()) {
 if (Test-Path -LiteralPath (Join-Path $evalRun $evalForm.Value)) {
  throw 'An operator form already exists; preserve it rather than overwriting evidence.'
 }
 if (-not (Test-Path -LiteralPath (Join-Path $evalPack $evalForm.Key))) {
  throw 'A staged template is missing; stop before copying or running cases.'
 }
}
foreach ($evalForm in $evalForms.GetEnumerator()) {
 Copy-Item -LiteralPath (Join-Path $evalPack $evalForm.Key) -Destination (Join-Path $evalRun $evalForm.Value)
}
Get-Content -LiteralPath (Join-Path $evalRun 'run-manifest.json')
& $evalPython scripts/evaluation_stage.py serve --root $evalRun
```

Keep terminal 1 running the scratch server at `http://127.0.0.1:8876`. In terminal 2:

```powershell
Set-Location -LiteralPath 'C:\Users\Ot\Downloads\EEE-Project\frontend\portal'
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8876'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Open `http://127.0.0.1:5175/portal` for this scratch run. All account/fixture IDs come from its generated manifest. A local port being busy is a blocked prerequisite, not permission to use the ordinary website. The template's application/firmware fields must be filled from this actual run.

### Optional private device/forwarded run

Defaults intentionally allow local-PC loopback hosts/origins only. For Android/iPhone or a forwarded PC case, use the existing VS Code private/authenticated forwarding workflow for **frontend port 5175 only**, and copy its exact HTTPS origin. No forwarding is opened by this pack. Do not forward the scratch database/backend separately, make the port publicly unauthenticated or alter normal production settings.

Stop the prior scratch server before restarting terminal 1 with the deliberately chosen frontend origin (origin only, without `/portal`, query, fragment or credentials):

```powershell
$evalOrigin = 'https://REPLACE-WITH-EXACT-PRIVATE-FRONTEND-HOST'
& $evalPython scripts/evaluation_stage.py serve --root $evalRun --frontend-origin $evalOrigin
```

Stop the previous local Vite process, then in frontend terminal 2 restart using the **same** exact origin:

```powershell
$evalOrigin = 'https://REPLACE-WITH-EXACT-PRIVATE-FRONTEND-HOST'
$env:__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS = ([uri]$evalOrigin).Host
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8876'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

The backend flag validates one HTTPS DNS origin and applies only scratch host/CSRF/link settings; the backend stays bound to loopback. Vite's extra-host variable takes the hostname, not a URL. Open the forwarded origin plus `/portal` on the intended device, complete the forwarder's authentication, then sign into the synthetic role. Record the actual origin, browser/OS and connection mode. Keep the link private; never use `*`, disable host/CSRF checks or silently reuse the ordinary website. If no valid origin/device/authentication is available, record BLOCKED and retain the error, not a cross-device pass.

### Link-only notification inspection

Follow MSG05 after creating a fresh current teaching message. In a third repository terminal while the servers remain running, set the **same** run path (change `run-001` if the actual run used another fresh name):

```powershell
Set-Location -LiteralPath 'C:\Users\Ot\Downloads\EEE-Project'
$evalRun = Join-Path (Get-Location) 'private-data\evaluation\2026-10-26\run-001'
.\.venv\Scripts\python.exe scripts/evaluation_stage.py capture-notifications --root $evalRun
```

It revalidates the scratch marker and isolated-memory backend, permits only synthetic example-domain recipients and stores generic teaching notification observations under private `evidence/`. It changes only scratch outbox rows and does **not** send SMTP or expose password/reset mail. A captured link notice is not inbox delivery or website reading; test explicit message opening separately. Record this as simulated/locmem transport, not a real-email result.

### Timing and optional physical work

After reviewing the real device/gallery/batch metadata, use the exact operation commands in [TIMING-SESSION.md](../../../hardware/fingerprint-diagnostic/TIMING-SESSION.md). The documented COM/scanner/batch placeholders are intentional. The harness's `--help` and synthetic self-check do not produce hardware timings. Do not automate repeated restore operations, erase galleries or mix a gallery-changing operation into a fixed-gallery recognition series.

For optional power/circuit/enclosure evidence, record the actual instrument, range/resolution, connection/method, operating mode, units and limitations in `physical-measurements-template.csv`. CAD dimensions, nominal datasheet current, a clock timeout or a guessed supply value are not measurements. Missing safe apparatus or assembly access is BLOCKED, not a reason to fill an illustrative result.

## Deferred discussion to revisit

On 26 October the owner deferred the Chapter Four attendance-import/integration discussion. Retain the staged cases as NOT RUN until actual observations are supplied. Ask later about scanner-file upload, class/meeting selection, identity matching and unresolved captures, review/finalisation, and the resulting per-student attendance rates. Continue the other report topics in the meantime.

## Subsequent owner-reported observations

On 26 October the owner confirmed that student-document upload, opening, download, replacement and staff approval were completely working. This is an operator-reported workflow result, separate from the staged synthetic cases above; no detailed case counts, timings or edge-case evidence were supplied. Retain the detailed CSV rows as NOT RUN until those specific cases are actually observed.

Owner checkpoint: course-material upload/student-download testing is blocked by an empty course selector (26 October). No material workflow outcome has been observed. Resume after a course offering and its teaching assignment are configured through the new HOD course interface. This observation does not mark any staged synthetic case as executed.

Owner checkpoint: HOD transfer, nominated staff acceptance and receipt of HOD access were reported successful on 26 October. This is a reported operational observation; detailed counts/timings and additional edge-case outcomes were not supplied. The separate staged synthetic-case ledger remains unchanged.

Owner checkpoint: full-semester GPA/CGPA calculation and comparison with manual calculation were confirmed successful on 26 October; status SUCCESS (owner-reported). Actual values, dataset counts and calculation worksheet were not supplied. This observation is separate from the unexecuted staged synthetic-case ledger.

Owner checkpoint: announcement publication and intended student/staff recipient visibility were confirmed successful on 26 October. Status SUCCESS (owner-reported). This does not confirm email delivery or all detailed staged message cases.

Owner qualification (26 October): announcement testing covered portal publication/visibility only. Email delivery/receipt is UNVERIFIED; confidence alone is not an observed result. Website message reading is reported incomplete, with future redesign/completion projected. Keep the portal visibility success separate from these outstanding outcomes. No specific backend failure or detailed read-tracking case has been established.

Material implementation check (26 October): reproduced and fixed the browser download HTTP 406 caused by an overly narrow CSV Accept header. Multipart upload, exact-byte student download, access/replacement/retry checks passed in isolated tests (15 teaching backend tests; complete portal suite 158 tests). Upload feedback and offering refresh were improved; build/lint passed. Owner material posting/student-download observations remain pending; staged case statuses are unchanged.

Owner timetable checkpoint (26 October): class-entry creation, assigned-staff/enrolled-student visibility and overlap warning with saving allowed were confirmed successful. Status SUCCESS (owner-reported). Counts/timings and detailed case evidence were not supplied; the staged synthetic-case ledger remains unchanged.

Owner guardian-result checkpoint (26 October): guardian result email delivery and opening its PDF with correct student details, results, GPA and CGPA were confirmed successful. Status SUCCESS (owner-reported); no detailed counts/timings or attachment evidence was supplied. Announcement email notifications and revised-result resend cases are not covered by this confirmation.

Owner student-access checkpoint (26 October): first-login password setup, subsequent sign-in and forgotten-password reset through the email link were confirmed successful. Status SUCCESS (owner-reported); detailed expiry/replay and negative-case outcomes remain separate.

Owner access-control checkpoint (26 October): student access to another student's private records and staff management of unassigned courses were reported correctly denied. Status SUCCESS (owner-reported) for those restrictions; exhaustive security coverage is not claimed.

Owner contact/guardian checkpoint (26 October): proposed detail changes remained pending without changing active values until authorised approval; confirmed successful. Status SUCCESS (owner-reported). Reviewer-role breakdown and detailed negative/history cases remain unspecified.

Owner archival checkpoint (26 October): student archival disabled login while preserving authorised staff access to records; confirmed successful. Status SUCCESS (owner-reported). Specific status variants and restoration cases were not individually identified.

Owner discrepancy-review checkpoint (26 October): prominent calculated GPA/CGPA, retained source values, reasoned adviser review and HOD notification were confirmed successful. Status SUCCESS (owner-reported). Specific numerical cases, notification channel and detailed evidence remain unspecified.

Owner revised-result checkpoint (26 October): correction of an already-sent result, a PDF marked Revised, and manual HOD confirmation/resend were confirmed successful. Status SUCCESS (owner-reported); no detailed counts, timings or failure/retry observations were supplied. The active Chapter Four now consolidates the reported outcomes while retaining outstanding cases separately.
