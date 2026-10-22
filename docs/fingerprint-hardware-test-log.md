# Fingerprint hardware transfer test log

Updated 15 October 2026. This records observed hardware results separately from
synthetic tests and planned experiments. No biometric payloads are included.

## Device and test setup

- Regular ESP32 development board; the upload tool identified ESP32-D0WD-V3,
  revision v3.1.
- AS608 model label supplied by the user; scanner firmware version unknown.
- UART pins RX GPIO16/TX GPIO17; console 115200 baud. The user's earlier scanner
  parameter report established communication at 57600 baud.
- The user designated slot 10 as the enrollment to use for this test.
- The portable record uses a generated test identity UUID. No student database
  association was made. Records remain in ignored private working storage.

## Experiment 1: initial slot-10 export and copy

| Check | Observed result | Scope of evidence |
| --- | --- | --- |
| Updated ESP32 firmware upload | PASS | esptool completed writes, verified flash hashes and reset the board |
| Export of occupied slot 10 | PASS | Firmware completed the EF01 data stream and the companion tool accepted its length/CRC |
| Exported payload length | 1536 bytes | Actual transferred opaque payload; applies to this export |
| Scanner-reported capacity/security | 150 slots / level 3 | Metadata read during export |
| Scanner-reported packet size | 128 bytes | UART chunk size, distinct from the total payload length |
| Saved record validation | PASS | Base64 decoding, byte count and SHA-256 checked again on resume |
| Restore into an additional free slot | PASS, slot 11 | Exact buffer and flash readback; original slot 10 preserved |
| Export/readback of restored slot | PASS | All 1536 bytes and SHA-256 equal the saved original; template/student UUIDs preserved |
| First selected-slot live scan after restore | NO MATCH | Image acquisition passed; Search returned 0x09; no matching score was available |
| Second-module or server-matcher compatibility | Not tested | No compatible second device/server matcher has been exercised |

Slot 10 was retained during this copy-only experiment. The successful export
establishes transfer and file integrity. It does not establish recognition
accuracy, a standard minutiae format, or a uniquely detectable student identity.
No stage latency was measured, so no transfer/recognition timing is reported.

## Experiment 1 session notes

On reconnecting on 15 October, the selected-slot firmware uploaded successfully.
The first restore attempt stopped while reading a partial console line; its
pending receipt has no selected slot and no template bytes were sent. The
Python line reader was repaired to assemble fragments within its bounded
deadline, and all ten Python tests passed.

A subsequent hardware check received ESP32 help output but scanner parameter
and template-count requests timed out. A full baud probe then received no
scanner response at any tested rate. After the user reseated power/UART wiring,
authentication recovered at 57600 baud and the module reported ten templates.
Restore into free slot 11 then succeeded. An independent export from slot 11
matched the original payload exactly, and the record UUIDs were retained.

The first subsequent selected-slot capture acquired an image successfully but
returned Search status 0x09 (no match). The initial diagnostic mislabeled a
no-match ACK containing result fields as a protocol error. It now accepts both
the status-only and five-byte no-match layouts without interpreting their
unused identity/score bytes. The synthetic suite covers both layouts. This
single trial establishes neither recognition accuracy nor a template-format
failure; the older slot-10 reference/finger association has not been independently
established in this test session.

The user requested a fresh two-scan enrollment before repeating backup, restore
and matching. Its first attempt timed out waiting for the initial finger image,
before model generation or storage. No new slot was saved on that attempt.

## Experiment 2: full erasure and restoration — 15 October 2026

The user subsequently exported a single-template library through the terminal
menu. The completed batch `export-20261015-091959-ec82003b` selected slot 1 and
contained one valid 1536-byte record. A fresh hardware inventory also contained
only slot 1. The record's student identity was unassigned; no database binding
was performed.

Before deleting anything, the assistant validated the record and manifest,
exported live slot 1 again, compared all bytes with the saved backup, and
rechecked that the backup covered every occupied slot. The user had explicitly
requested erasure and restoration.

| Check | Observed result |
| --- | --- |
| Before erasure | 1 occupied slot, ID 1 |
| Backup versus live data before erasure | PASS; all 1536 bytes equal |
| Scanner Empty command and count check | PASS; `ERASED: stored templates=0` |
| Independent occupied-slot list after erasure | Empty; 0 occupied slots |
| Restore from saved bytes | PASS; stored in slot 1 with exact flash readback |
| Independent export after restoration | PASS; all 1536 bytes and SHA-256 equal backup |
| Final occupied-slot list | Exactly slot 1; 1 stored template |
| Template UUID | Preserved |
| Gallery namespace | New UUID recorded after full erasure; local export profile updated |
| Fresh live-finger recognition after this erasure | Pending user terminal test |

The private operation journal is
`private-data/fingerprint-templates/erase-restore-20261015-092600-7684f454/verification.json`.
It records preflight checks, erasure, restoration mapping, byte verification and
the namespace change without embedding the biometric payload.

This experiment demonstrates actual library erasure and template restoration
with byte integrity. Recognition remains a separate check: the user should run
`m` in Serial Monitor and present the finger corresponding to the backup.
Since only the restored template exists, a returned ID 1 demonstrates a match
to that restored reference. No new enrollment is needed for this check.
One successful recognition trial would establish operation, not a population
accuracy estimate or interoperability with another sensor/server matcher.

Use the [storage design](fingerprint-template-storage.md) for transfer details
and the [evaluation reference](fingerprint-score-and-evaluation-reference.md)
for score interpretation, denominators and report wording.

## User-run accuracy preparation — 15 October 2026

A subsequent pasted terminal transcript shows successful upload of the separate
`esp32-accuracy-identify` build, recorder schema handshake and summary collection.
No ground-truth block was started in that recorder run: all attempt counts were
zero. It therefore verifies connection/recording startup, not biometric accuracy.
Repeated Ctrl+C interrupted recorder shutdown; the Python cleanup was corrected
and its synthetic regressions pass, with physical retry pending.

The user then uploaded the normal `esp32` firmware. Its scanner report/list
showed four occupied slots, IDs 1–4, at the existing 57600 baud, capacity 150 and
security level 3. The last two diagnostic matches each completed image capture,
feature extraction and search and returned slot 2. Use the finger presented in
those scans as the candidate genuine reference for the next 1:N block, with
expected ID 2. These two setup matches are not a controlled accuracy dataset
and do not identify the owners of slots 1, 3 or 4.

The optional attendance filesystem failed to mount and RTC I²C reads failed in
the normal firmware. Those components are not used by the separate accuracy
build. No formatting/erasure or repair of those data stores was performed.
The transcript also includes raw template exports; biometric payloads are not
copied into this shared test log and no new verified JSON backup is inferred
from Serial Monitor output alone.

## Controlled 1:N genuine block — 15 October 2026

The next user-run capture, `run-20261015-130414-UTC-61ac126d`, contains ten
automatic genuine presentations in session `E7E18433-4`, with expected ID 2.
All ten returned ID 2. The scanner reported security level 3, four stored
templates and capacity 150 throughout the block.

| Measurement | Observed result |
| --- | --- |
| Attempts / completed decisions | 10 / 10 |
| TP / FN / wrong identity | 10 / 0 / 0 |
| Acquisition / communication / sensor errors | 0 / 0 / 0 |
| Poll errors / unclassified attempts | 0 / 0 |
| Genuine recognition / observed genuine failure rate | 10/10 (100%) / 0/10 (0%) |
| Impostor presentations | 0; false-positive rate and specificity not evaluated |
| Trial recording | Continuous event IDs 1–10; summary agrees with trial rows |
| Recorder issues | Empty issues log; complete final summary |

This block was conducted under instructions to keep the same known slot-2
finger throughout. The CSV records returned identities, not independent proof
of which physical finger was presented. Ten repeated presentations of one
finger do not establish population-wide accuracy or a zero underlying error
rate. They also do not verify recognition of the restored slot-1 template from
the separate erasure/restoration experiment.

An earlier mixed-finger capture (`run-20261015-125013-UTC-4b54bda6`) is excluded
from the controlled genuine estimate: the user confirmed switching fingers
while expected ID 2 remained selected. That capture also had a missing/corrupt
trial and an incomplete final summary response. Its private review preserves
these limitations; it is not pooled with the ten-presentation block.

## Controlled 1:N impostor block — 15 October 2026

The user confirmed having a finger known not to be enrolled anywhere in the
current library. Capture `run-20261015-131914-UTC-0a433c09`, session
`BCADF5D5-2`, records ten automatic impostor presentations. All ten completed
Search with no-match status `0x09`: TN 10, FP 0. Acquisition, communication,
sensor and polling errors were all zero; no attempts were unclassified.
Event IDs 1–10 are continuous, the trial rows agree with the complete summary,
and the recorder issues log is empty.

Both controlled blocks report security level 3, gallery count 4, capacity 150,
57600 baud and occupancy CRC32 `5D37E4F3`. The ESP32 boot/session changed between
captures. Matching occupancy/settings do not prove unchanged template bytes;
the comparison assumes no intervening scanner/reference changes.

| Case | Attempts | TP | FN | TN | FP | Observed case error rate |
| --- | --- | --- | --- | --- | --- | --- |
| Genuine, expected ID 2 | 10 | 10 | 0 | 0 | 0 | 0/10 genuine identification failures |
| Unenrolled finger | 10 | 0 | 0 | 10 | 0 | 0/10 false-positive identifications |
| Combined across the two captures | 20 | 10 | 0 | 10 | 0 | 20/20 correct completed decisions |

Observed decision accuracy and coverage are 100% in this small, balanced sample.
The observed false-positive and genuine-failure rates are each 0/10 (0%), not
proof of zero underlying error. Repeated presentations of one finger per case
do not establish population-wide accuracy. This completes the initial 1:N
smoke test; the separate selected-slot 1:1 experiment follows below.

## Selected-slot 1:1 genuine failure — 15 October 2026

Capture `run-20261015-132248-UTC-dad97a78`, session `D868824A-2`, contains
ten automatic genuine trials against slot 2 in `verify_1to1`. The user explicitly
confirmed presenting the same enrolled slot-2 finger that passed the earlier
1:N block. All ten completed image/feature processing and returned Search
no-match status `0x09`: TP 0, FN 10. There are no impostor trials in this run,
so false-positive rate and specificity remain unevaluated for 1:1.

Acquisition, communication, sensor and polling errors are zero. Event IDs 1–10
are continuous, trial rows agree with the complete summary, and the recording
issues log is empty. The configuration again reports security 3, four stored
templates, capacity 150 and occupancy CRC32 `5D37E4F3`. This verifies settings
and occupied positions, not the template bytes or physical finger identity.

The firmware uses Search command `0x04` with start slot 2 and count 1 for this
test, versus start 0 and count 150 for the earlier whole-library test. Code
inspection confirms those ranges are encoded as intended. This result does
not establish why the selected-slot search failed: current full-library
recognition, reference continuity and sensor behavior still require hardware
checks. Repeat a short whole-library block using the same finger before
continuing the selected-slot experiment. Preserve this failed run rather than
pooling it with successful 1:N trials or silently replacing its labels.

## Whole-library diagnostic repeat — 15 October 2026

Capture `run-20261015-132533-UTC-839ce02c`, session `E2B750CC-2`, contains
three genuine attempts with expected ID 2. The first two returned ID 2 (TP 2).
The third returned status `0x17` at Search and is recorded as a sensor error,
outside the confusion matrix. FN is zero; completed-decision coverage is 2/3
(66.6667%). Calling this run three successful matches would be incorrect.
Trial IDs 1–3 are continuous, summaries agree, and the issues log is empty.
Reported settings and occupied-slot CRC remain the same as the preceding runs.

These results show continued whole-library recognition of slot 2 but do not
alone establish why selected-slot Search failed. A one-image `q` diagnostic
was added to compare full Search, selected Search and LoadChar/Match without
counting statistics. Explicit `e` enrollment was also added at the user's
request so a fresh reference can be tested in a new session. Physical results
for these new commands remain pending.

## First RTC connection — 15 October 2026

User-run capture `run-20261015-180803-UTC-0587016c` reports DS1307 local time
initially in 2000, followed by explicit PC synchronization, `ACCRTC SET VERIFIED`
and a valid read of 2026-10-15T19:08:04 with UTC offset +60 minutes. This
establishes a successful clock write/readback, not a ten-second advancing-clock,
long-term drift or power-off retention result.

The same boot reports scanner communication baud 0 (no authenticated scanner
connection), and no fingerprint trials were recorded. The shared unavailable/
empty-library message does not establish that stored templates were erased or
that the library is empty. The next hardware check is a `b` scanner probe,
followed by power/UART wiring checks if authentication remains unavailable.

## Fresh single-reference 1:N pilot with RTC — 15 October 2026

The user confirmed Empty completed with stored count zero, then enrolled one
finger in slot 1. A normal diagnostic returned slot 1 for that finger and no
match for a different unenrolled finger. The controlled capture is
`run-20261015-184034-UTC-6743beef`, session `3A718FF9-3`. These are new references
and a one-template gallery; do not pool with earlier four/seven-template runs.

Both blocks report capacity 150, security 3, stored count 1, 57600 baud and
occupancy CRC32 `AEBCCF9E`. The user followed ten genuine presentations of the
enrolled slot-1 finger and ten presentations of the same designated unenrolled
finger. This is a single-person, one-positive-finger/one-negative-finger pilot.

| Case | Automatic attempts | TP | FN | TN | FP | Median total_ms (range) | Median search_ms (range) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Genuine | 10 | 10 | 0 | 0 | 0 | 897.5 (868–1014) | 47.5 (43–127) |
| Unenrolled | 10 | 0 | 0 | 10 | 0 | 981.5 (958–1017) | 109.5 (73–119) |

All twenty attempts completed decisions, with no acquisition, communication,
sensor or polling errors and no unclassified outcomes. Observed accuracy and
coverage are 20/20 (100%); observed genuine failure and false-positive rates
are each 0/10 (0%). These are sample observations, not demonstrated zero
underlying error probabilities. total_ms excludes human waiting and the
two-second cooldown; search_ms measures only the Search transaction.

Independent CSV validation found continuous event IDs 1–20, valid trial and
summary arithmetic, exactly one timestamp per trial and an empty recording
issues log. The saved session includes 33 post-sync RTC readings: all have
valid status/date and nondecreasing time from 19:40:34 through 19:44:27 local
UTC+01:00. RTC-minus-PC receipt time ranges from -1.964 to -1.038 seconds,
median -1.547 seconds. This includes RTC one-second quantization and serial/
host receipt latency; it is not a calibrated clock accuracy/drift measurement.

The file also retains an incorrect year-2000 reading in an earlier, pre-sync
session. It is excluded from post-sync timing claims, not deleted. No calendar
reset occurred within the validated post-sync session. Battery retention and
long-term drift remain untested. Selected-slot/direct comparison of this fresh
reference is the next diagnostic, followed by a separately labelled 1:1 block.

## Same-image comparison of the fresh reference — 15 October 2026

The user supplied a `q` diagnostic for target 1 in session `3A718FF9-4`.
GetImage and each of three GenChar calls succeeded. The original fixed sequence
produced full-library Search success/ID 1, selected-slot Search no match (`0x09`),
LoadChar into buffer 2 success, and direct Match no match (`0x08`). All commands
had valid transport/ACK frames. No diagnostic accuracy attempts were counted.
The subsequent RTC read was 2026-10-15T19:47:32, status ok, UTC offset +60.

This demonstrates differing outcomes within that diagnostic sequence, not why
they differ. Repeated feature generation or preceding comparisons could affect
internal scanner state. The updated q command rotates comparison order across
fresh captures so each method can run first, and prints the exact requested
Search range. Statistical Search behavior is unchanged; no template is modified.
Physical results for the rotating-order diagnostic remain pending.

## Diagnostic processing dependence observed — 15 October 2026

The user supplied all three rotating-order captures for enrolled slot 1:

| Sequence | First method | Subsequent operations |
| --- | --- | --- |
| Selected / direct / full | Selected Search matched ID 1 | Direct Match returned 0x08; third GenChar returned 0x07, so full Search did not run |
| Direct / full / selected | Direct Match succeeded | Full and selected Searches each returned 0x09 |
| Full / selected / direct | Full Search matched ID 1 | Selected Search returned 0x09; direct Match returned 0x08 |

Thus each method can succeed when it is the first comparison after capture.
The repeated-processing diagnostic cannot support independent comparisons of
the later methods. This is consistent with state/image mutation during repeated
feature generation or comparison; the exact mechanism is not established.

The diagnostic was corrected to run one feature extraction and one method per
fresh image, cycling selected Search, direct Match and full Search across q
requests. No statistical counters or stored templates are changed. The normal
accuracy workflow already used one extraction and one Search per image and
is unchanged. Earlier genuine-labelled 1:1 failures remain retained, with their
cause unresolved; they cannot all be attributed to this separate q defect.
A new controlled 1:1 block of the fresh slot-1 reference remains necessary.

## Fresh single-reference 1:1 pilot with RTC — 15 October 2026

Capture `run-20261015-185538-UTC-056c1ba8`, session `22ACA06F-3`, contains
ten genuine and ten designated-unenrolled attempts against slot 1. The user
followed instructions to use the same genuine/negative fingers as in the 1:N
pilot. All genuine trials returned slot 1 and all negative trials returned no
match: TP 10, FN 0, TN 10, FP 0. No acquisition, communication, sensor or polling
errors or unclassified attempts were reported. Gallery count 1, capacity 150,
security 3, 57600 baud and inventory CRC AEBCCF9E match the preceding pilot.

Independent validation confirmed twenty continuous trial IDs, matching summary
arithmetic, exactly one timestamp per trial and an empty recording issues log.
Median total/search time was 923.5/59.5 ms for genuine trials and 920.5/85.5 ms
for negative trials (n=10 per case). Total ranges were 864–966 and 789–966 ms;
Search ranges were 45–100 and 46–96 ms respectively.

All 23 post-sync RTC records (20 trial-linked plus checks) have valid date/status
and nondecreasing time from 19:55:38 to 19:58:24, UTC+01:00. RTC minus PC receipt
time has median -0.896 seconds and range -1.381 to -0.423 seconds. Quantization
and receipt latency apply; this is not a calibrated clock/drift or battery
retention result. Explicit sync at this run's start prevents inferring retention
between the 1:N and 1:1 runs.

The two fresh controlled pilots are summarized in
[fingerprint-pilot-results.md](fingerprint-pilot-results.md), with per-method
denominators, processing times, RTC checks and sample limitations. Older failed
experiments and diagnostic sequences remain separate historical evidence.


## Probe-test preparation — 16 October 2026

- Connected regular ESP32-D0WD-V3 on COM12, revision 3.1, 4 MB flash.
- Initial flash read returned FF/FFFF with peripherals attached; identification
  succeeded after the user disconnected external wiring. The specific offending
  connection is not established.
- Long backup reads stalled; bounded sections at 115200 baud completed. One
  section failed its digest check and passed on retry. A full private 4 MB
  recovery image and SHA-256 are retained under private-data/device-backups.
- Generated partition table matched the backed-up board exactly.
- Uploaded esp32 profile at 115200 baud; flash write hashes verified successfully.
- Read-only console check confirmed q/j capture-and-later-compare commands.
- No probe was captured and no physical comparison result exists yet. Scanner
  reconnection is the next step. Its enrolled library was not modified.


## Preliminary single-probe comparison — 16 October 2026

- Scanner reports capacity 150 and occupied slot 1 only.
- Exported a single-capture 1536-byte probe into ignored private storage.
- Saved-probe Search after reported power cycle: NO_MATCH; exact buffer readback
  and unchanged slot inventory verified. No measured no-match score is available.
- Fresh live control: MATCH, raw unitless score 198. An earlier timed-out control
  is incomplete, not a recognition rejection.
- Added direct buffer comparison (probe in buffer 1, reference in buffer 2).
  Host/C++ fixtures pass. The saved positive probe matched with raw score 41.
- An interrupted 115200 application update was repaired at 57600; flash hash
  verified. This does not erase or write the separate scanner's template library.
- First different-finger capture attempt did not produce a valid probe. Capture
  waits extended from 20 to 60 seconds for coordination and diagnostics improved.
- Final direct-mode validation of both probes after a scanner power cycle remains
  pending. No FAR/FRR or production matching capability is established yet.


## Completed saved-probe physical controls - 16 October 2026

Supersedes earlier pending-hardware notes. ESP32 on COM12 ran q/j/k firmware
with 60-second finger waits. Both saved captures were 1536 bytes. After an
operator-reported USB power cycle, direct buffer Match compared saved data
against slot 1: positive MATCH (raw score 41), negative NO_MATCH (no measured
score). No fresh readings were taken. Inventory before/after was [1], capacity
150. A final report is saved in ignored private-data/fingerprint-probes.

Earlier saved-probe Search returned NO_MATCH despite a live MATCH (score 198).
Use the validated direct 1:1 method for this unit; do not assume Search
portability. These are feasibility controls, not an accuracy study or laptop-only
matcher. No attendance marks or database writes were made.


## Deferred capture implementation - 16 October 2026

Added the isolated esp32-deferred profile, bounded binary header/event files,
per-event staged write/readback/rename verification, lift-gated autonomous
capture, reboot-disarmed state, USB framed download, JSONL validation and
exclusive local output creation. Device files are retained. No student attendance
is inferred from capture or download. Boot UUID/elapsed milliseconds are stored;
wall-clock time remains unresolved. See DEFERRED-CAPTURE.md for the contract.

Validation: 12 deferred downloader Python tests, 20 portable-template Python
tests and 10 probe Python tests pass (42 total). Native format/storage and
actual device-controller tests pass under C++11 -Wall -Wextra -Werror, including
held-finger deduplication, reboot/export persistence, torn writes, corruption,
full storage, missing filesystem and refusal to initialize any non-erased raw
partition. The existing native probe-comparison suite also passes. A synthetic
native header was decoded by the Python host. The esp32-deferred build succeeds:
50,768 bytes RAM and 346,165 bytes application flash.

Application-only upload to COM12 at 57600 passed flash hash verification. The
partition table matches the original verified recovery image. The live filesystem
partition was verified entirely erased before explicit initialization succeeded.
The first initialization host receipt encountered an oversized SDK diagnostic;
the host now accepts bounded diagnostic lines before receipts while retaining
strict transfer-block bounds. No automatic format-on-mount-failure was enabled.

Physical empty-batch creation/reset/download remains pending: the AS608 did not
respond to a subsequent full baud probe, although the ESP32 console works. Last
successful scanner inventory was [1], capacity 150 before this update. No new
captures, sensor enrolment writes/deletions or backend/database changes were
made in this step. Capture is stopped pending the operator's wiring/power check.


## Empty offline-batch hardware check passed - 16 October 2026

The operator confirmed the AS608 had been disconnected, then reconnected it.
UART authentication and inventory checks passed: occupied slot [1], capacity 150.
Physical batch creation exposed a trailing directory separator incompatibility
with LittleFS. Directory paths now omit that trailing separator; the native
filesystem fixture rejects it so the regression is covered. Native controller
tests pass and the corrected ESP32 build uses 50,768 bytes RAM / 346,233 bytes
application flash. Application-only upload at 57600 passed hash verification.

A new batch with a synthetic class-session UUID was created on the device,
exported over USB and checked locally. After an ESP32 reset (not a full power
cycle), the same empty batch exported identically; both JSONL files validated.
Scanner inventory was still [1], capacity 150. Device files were retained.
The initialized filesystem was preserved through the application update.

No live capture or attendance mark was created. The next physical check is one
live enrolled-finger capture, persistent save, power cycle, USB download and
saved-probe direct comparison. Capture remains disarmed awaiting operator readiness.
This entry supersedes the earlier disconnected-scanner checkpoint.


## Live deferred capture power-cycle test passed - 16 October 2026

One enrolled-finger capture was committed to ESP32 LittleFS and downloaded
before the operator unplugged/reconnected USB. After that reported power cycle,
the single committed event downloaded byte-for-byte identically, including its
event UUID and file digest. Probe size: 1536 bytes. Direct AS608
buffer comparison of those downloaded bytes against slot 1 returned
MATCH, raw unitless score 80. No fresh capture
was taken during verification. Inventory remained [1], capacity 150.

Capture is stopped. Device files and private downloads are retained. The batch
uses a synthetic class-session UUID and produces no real student attendance or
database writes. This validates the live capture/save/power-cycle/download/direct
comparison path on this unit. It does not validate population identification,
software-only matching, physical brownout during a write, or FAR/FRR.
See docs/attendance-device-handoff.md (from repository root) for the next step.
