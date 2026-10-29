# Attached-terminal test checkpoint - 28 October 2026

This is a partial physical test checkpoint, not completion of all outstanding evaluation.

## Conditions

- Regular ESP32 terminal found on COM12 through CP210x. Scanner: capacity 150, security level 3, UART 57600 baud; console 115200 baud.
- One reference in slot 1. No reference was erased, enrolled or restored; no firmware or filesystem was formatted.
- Biometric payloads and detailed records are retained only in ignored private-data/terminal-tests/session-20261028T095616Z/.

## Completed checks

| Operation (three repeats) | Median (ms) | Range (ms) |
| --- | ---: | ---: |
| Reference response reception and validation | 679.759 | 676.827--679.804 |
| Saved batch reception, validation and JSONL construction | 606.111 | 605.548--608.158 |
| Host file save and readback | 6.858 | 6.110--28.343 |
| Saved-probe upload/readback/direct comparison transaction | 2121.356 | 2120.358--2121.495 |

The intervals exclude port connection unless stated by the timing harness. They are not pure sensor-matcher timings or complete attendance throughput.

- All three reference exports had identical payload hashes.
- One existing batch with one committed capture and no pending-write flag downloaded three times; snapshots were identical.
- Three direct comparisons of that pre-existing probe returned NO_MATCH. Its current physical finger identity was not re-established, so these are diagnostic outcomes, not false-negative estimates.
- Loopback HTTP with a synthetic assigned-staff account: preview returned 200; import returned 201; exact retry returned 200 with the original receipt.
- The backend preserved exact probe bytes and presented the unresolved capture as archived. No automatic attendance record was created.
- The isolated evaluation database and local-memory email backend were used; no live student data or real messages were changed.

## Attempt notes and remaining work

- The first live probe acquisition reached the host but the recording wrapper used an incorrect metadata field and failed before saving (KeyError). The error record is retained; this attempt is not an accuracy-trial result.
- The corrected acquisition window ended with no finger detected. This is a timed-out readiness/capture attempt, not an established genuine comparison.
- Fresh enrolled/unenrolled controls require the operator to be ready at the scanner.
- Full physical-to-resolved-attendance promotion, RTC/power retention, UI feedback and interruption during an active write remain open.
- No 31-person repeat trial, population accuracy claim or reconstructed scan ledger is implied.

## Fresh controls and physical class chain completed

- A fresh operator-designated enrolled finger produced a saved 1536-byte probe and direct MATCH against slot 1. The comparison transaction took 2103.416 ms (including upload/pacing/readback, not pure matching).
- After undetected placement/readiness windows (preserved in the private records), a fresh known unenrolled finger produced a saved 1536-byte probe and NO_MATCH; transaction 2165.670 ms. The operator confirmed a steady placement during one failed detection window. No-finger timeouts are not treated as correct rejections or silently dropped.
- A new device batch was prepared for a synthetic approved class. One fresh enrolled capture was saved and stopped, downloaded and validated, then compared directly with slot 1: MATCH (2106.434 ms transaction).
- The fresh batch download receive/validation phase took 607.994 ms; local save/readback 5.472 ms. Each is one observation.
- Authenticated loopback HTTP preview/import returned 200/201. The capture initially remained archived, with no automatic attendance.
- The slot-to-synthetic-student binding, scanner result and host capture time within the synthetic meeting were explicitly reviewed. Device calendar time remained unverified for that record.
- Review resolution, collection closure and explicit meeting finalisation succeeded. One student/one meeting produced one attendance record and a final rate of 100.00%, with zero pending meetings. This is a fixture result, not population recognition accuracy.
- Replaying the file and resolution, including after finalisation, retained exactly one attendance record and the import receipt.
- No live student attendance, external email or shared database was changed. This proves the tested scanner-assisted/manual-review HTTP path; it does not implement automatic matching or validate the browser/production deployment.

## RTC pre-power reference

The clock fields read through the menu without saving were 2026-10-28 11:17
(Lagos local time, minute resolution), with host reference 2026-10-28 10:18:46 UTC.
The discrepancy and minute resolution are retained; this is not a clock calibration.
A complete-main-power removal check was requested after all capture files were saved.

## Retention and core continuation

- Operator reported approximately 65 seconds with USB and all main supply disconnected, retaining the RTC backup cell. The RTC retained the correct date and advanced from 11:17 to 11:21 local at minute resolution; the elapsed RTC/host difference was approximately 17.4 seconds within this coarse reading. No clock reset was performed; this is functional continuity, not calibrated drift.
- The committed capture downloaded byte-identically after reconnection. Slot 1's reference export was also identical, and the saved genuine probe still returned MATCH.
- Normal immediate mode reported ATTENDANCE SAVED; the operator confirmed the display, green LED and short beep. One duplicate attempt first failed acquisition (recorded, not discarded). A subsequent attempt reported ALREADY CHECKED IN; the operator confirmed the display, red LED and two beeps. Local CSV rows stayed at 56 and its exported contents were unchanged by the failed/duplicate attempts.
- Restarting the isolated backend retained the physical capture, one attendance record and finalisation.
- A second distinct enrolled capture in the same class matched slot 1. Appending it invalidated the previous finalisation and withheld rates. Explicit review resolved both events to the same synthetic student, retaining one attendance record and a 100.00% one-meeting fixture rate. Old-file retries preserved the appended evidence.
- A third physical capture, from the known unenrolled control, returned NO_MATCH. Import left it archived with no student binding or automatic attendance. The existing one attendance record remained; no absence row was created. Finalisation became stale and the rate was withheld until renewed review. The unmatched event was deliberately left unresolved.
- Final synthetic state: three capture events (two resolved to the same student, one archived), one attendance record, no false absence, one pending meeting and no current final percentage. The earlier 100.00% rate describes the explicitly finalised stage before the unmatched evidence arrived.
- Testing stopped at the operator's request for selection of remaining checks. The terminal is paused. No enrolled reference or existing capture was erased; no live student database was changed.

## Remaining checks for operator selection

1. Controlled main-power interruption during an active save, with a verified current backup/recovery plan.
2. Interrupted USB download and safe retry into a new host file.
3. Full browser staff/student walkthrough of the physical-capture review path (HTTP backend path has passed).
4. Wrong-class and unauthorised-user rejection using the actual terminal file.
5. Physical Immediate/Deferred switching, Start/Stop and reboot-with-capture-stopped behaviour.
6. Optional larger logged recognition study, precise RTC drift and detailed electrical/endurance measurements.

## Selected checks 3 and 2: browser walkthrough and USB interruption

- The isolated portal was served at 127.0.0.1:5176 against the scratch backend; the live portal was left unchanged. The synthetic assigned staff account signed in, listed the available classes and displayed the single present record for the physical-capture class.
- The browser upload/review/student walkthrough is PARTIAL, not passed: the in-app file-chooser integration failed before selection, and the native browser fallback stopped when the automation tool could not verify the Windows browser URL. This is a tool blocker, not an established application failure. File preview/import, finalisation through the browser and student attendance display remain unverified in this walkthrough.
- A deliberate host-side USB serial disconnect was triggered inside an event transfer after 1209 wire bytes (657 within the event phase). No complete JSONL file was published; the wire prefix was retained privately.
- A fresh complete retry recovered all three captures byte-identically to the pre-interruption snapshot. A second download was identical. The isolated backend returned the original receipt on replay (HTTP 200), without new attendance effects.
- The first check compared the current inventory to an older one-slot checkpoint and stopped its final assertion. The operator confirmed adding two references independently. The conclusive repeat used a fresh inventory: slots [1, 2, 3] before and after. All three references and device files were preserved.
- This passed test is a closed host serial connection during real transfer; it is not a physical cable-unplug test or power interruption during device flash writing.

## Guided browser walkthrough completed

After automation was stopped, the operator continued in the isolated portal with
step-by-step guidance. Supplied screenshots showed one present record, two
resolved captures and one archived capture. The finalisation screenshot showed
"Reviewed and finalised", revision 3, with ATT-001 present. The operator then
confirmed success after checking the retained archive, signing out, signing in
as the synthetic student and opening Attendance.

The selected staff-review/finalisation/student-display walkthrough therefore
passed through operator-guided interaction. Browser file selection, preview and
import controls were not exercised; the physical file's authenticated HTTP
import/retry checks passed separately. This closes the earlier browser
walkthrough blocker for the selected review/display scope without claiming a
browser upload test that was not performed.

## Browser file controls completed by the operator

The operator selected the original three-capture JSONL in the isolated staff
portal, previewed it, acknowledged review and imported the same bytes. The
supplied screenshot showed 3 captures, 0 new events, 3 existing events, recovery
review not flagged and "Original receipt recovered". It explicitly stated that
no attendance marks were created. An unchanged copy of the screenshot is retained
with private browser evidence.

This completes the previously pending browser file-selection/preview/import
controls, alongside the guided staff finalisation and confirmed student view.
Selected checks 3 (browser walkthrough) and 2 (host-side interrupted USB download
and validated retry) have now passed within the isolated test scope.

## Final owner-confirmed reconciliation

The owner confirmed personally completing the remaining active-save power-loss,
wrong-class/unauthorised-import and physical mode-control checks offline, in
response to the completion/pass-status question. They are marked owner-reported
passed; no stage trace, rejection ledger or run-level record was supplied here.
The agreed prototype checklist is complete, with logged and owner-reported
outcomes distinguished. The report results, abstract, methodology, appendices,
conclusions and completion checklist have been reconciled accordingly. Wider
field qualification and instrumented studies remain further work.
