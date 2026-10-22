# Attendance device checkpoint - 16 October 2026

Continue from this checkpoint; inspect current source before editing. This is a
local prototype with uncommitted work, not a deployed attendance integration.

## Verified hardware and physical results

- ESP32-D0WD-V3, 4 MB flash, CP210x serial bridge on COM12. Not an S3 N16R8.
- AS608 reports capacity 150 with one enrolled reference, slot 1.
- Working UART wiring: scanner TX to GPIO16, RX to GPIO17; common ground.
- Previously exported positive and negative probes, after a power cycle:
  direct comparison against slot 1 yielded MATCH and NO_MATCH respectively.
  Single-slot Search did not work for the saved positive probe; use direct Match.
- A live capture was saved on ESP32 LittleFS, downloaded, then downloaded again
  after an operator-reported USB power cycle. The files were identical. Direct
  comparison of the saved data returned MATCH, raw unitless score 80.
- No fresh finger reading was taken during that final comparison. Gallery
  membership remained [1]. Capture is stopped; device files remain saved.
- This is a feasibility test, not an accuracy study or a software-only matcher.
  Electrical power loss during an unfinished write remains untested physically.

## Implemented device layer

- `hardware/fingerprint-diagnostic/platformio.ini`: isolated `esp32-deferred`
  profile; legacy attendance UI disabled. Regular diagnostic profile remains.
- `include/deferred_format.h`: bounded big-endian binary header/events and
  CRC32; staged commit with readback, rename and final readback.
- `include/deferred_device.h`: class-bound batches, autonomous lift-gated
  capture, persistent per-event files, explicit re-arm after reboot, no automatic
  deletion, interrupted-write detection and read-only USB export.
- `tools/deferred_batches.py`: begin/arm/stop/list/download/validate commands;
  complete stream SHA-256; exclusive JSONL output with readback validation.
- An explicit initialization command formats only a partition whose entire
  live contents were verified erased. Mount failure never triggers formatting.
- Physical testing found and fixed trailing separators on LittleFS directory
  creation; the native filesystem fixture now rejects that regression.
- Installed firmware is `esp32-deferred`; application-only upload at 57600.
  Partition table matched the verified original recovery backup. No later
  filesystem wipe is needed or authorized by this checkpoint.

See `hardware/fingerprint-diagnostic/DEFERRED-CAPTURE.md` for commands and format.

## Validation and private state

42 Python tests passed: 12 deferred-batch, 20 template-portability, 10 probe.
Native format/storage, device-controller and saved-probe suites passed under
C++11 with warnings as errors. The final ESP32 build passed. No backend code
was changed during the device implementation; no shared DB migrations applied.

Private payloads/downloads and the detailed physical test session are in ignored
`private-data/fingerprint-probes/offline-test-*/session.json`. Select the newest
folder containing that file. Its stage is
`live_persistence_and_comparison_complete`. The class-session UUID is synthetic;
never use that batch to create real student attendance. Do not print or commit
probe bytes/Base64, private files or recovery-image contents.

Original full-flash recovery image is retained under
`private-data/device-backups/bounded-20261016-110518/`.

## Agreed attendance behavior

- Sessions belong to course offerings; HOD confirms each offering's roster once
  per academic session/semester. Each class snapshots that approved roster.
- Candidate roster combines active students at that level with latest verified
  failed prior attempts for HOD review; failure does not prove registration.
- HOD and staff explicitly assigned to the course manage sessions/corrections.
- Capture unidentified probes offline without preloading a gallery per class;
  resolve identities later. A saved scan alone is never attendance.
- Use Student UUIDs internally and matric identifiers for display. Neither
  template hashes nor scanner slot numbers are stable student identities.
- One attendance record per student per class; retries preserve event UUIDs.
- Warning threshold initially 75%; exactly 75% qualifies. Exclude cancelled
  classes and formally excused classes from the relevant denominator. Pending
  reconciliation must not generate false absences or warnings.
- Exam/test identification uses reviewed filtered reference galleries. Capacity
  150 concerns reference slots, not ESP32 capture-file count. Never automatically
  wipe a gallery when reaching 150 scans; preserve backups and slot bindings.

## Backend continuation - 16 October 2026

The next checkpoint step is implemented locally: authorized pending-batch
preview/import and paginated metadata listing under each real class session.
See [attendance-pending-batches.md](attendance-pending-batches.md) for the raw
JSONL API, restricted permission and preview-digest upload example.

The parser independently bounds files/lines/events/probes and validates the full
schema and trailer. Events are immutable, ordered and append-only per batch;
exact retries return the original durable receipt, including after newer
snapshots. Conflicting UUID/data reuse rejects the complete transaction.
Interrupted-write review is sticky. Times remain null with exact boot/uint64
uptime evidence. No student identity or attendance is inferred from an upload.

Migration attendance/0003 is generated; only isolated synthetic test databases
were migrated. The firmware, scanner gallery, device files, recovery backup and
private physical-test payloads were unchanged. Device authentication, encrypted
biometric storage/key management and retention policy remain unfinished.

Validation: 316 backend tests passed on isolated SQLite, including 36 new pending
batch tests and the 30 existing attendance tests. All 62 hardware Python tests
passed; the temporary-file hard-link check required running outside the Windows
sandbox. Django system checks, missing-migration checks and whitespace checks
passed.

Extended validation then passed all 337 backend tests on isolated PostgreSQL
16.15, including 14 real lock-contention cases and seven session-authenticated
HTTP cases. Fresh application-process restart preserved login and receipt
identity. These tests exposed and fixed an HTTP 415 failure in the raw JSONL
session/CSRF path, plus content-type parameter handling. See
[attendance-validation.md](attendance-validation.md) for coverage and rerun
commands. The temporary PostgreSQL server was stopped and its successful test
cluster removed. React browser interaction, sustained load and physical field
tests remain pending; no device or shared-database changes were made.

## Next implementation

1. Define restricted biometric enrollment-to-student bindings and compatible
   scanner-assisted matching orchestration. Review unknown, ambiguous and
   out-of-roster outcomes before attendance writes. A single positive match is
   not proof of unique identity across an untested population.
2. Reconcile resolved, eligible students through existing attendance services,
   deduplicating per class and preserving audit history.
3. Add trusted clock provisioning/RTC integration: current records deliberately
   have null captured_at, plus boot UUID and elapsed milliseconds.
4. Implement closed/reconciled class metrics, excused/cancelled states and 75%
   warnings; then connect React and finish device authentication/field tests.

The existing backend attendance models/services/APIs are under `app/attendance/`.
Requirements and API notes are in `docs/attendance-device-workflow.md`,
`docs/attendance-api.md` and `docs/attendance-implementation-plan.md`.
The teammate's result importer is separate work to integrate later.
