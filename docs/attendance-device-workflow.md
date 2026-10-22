# Attendance device workflow — 16 October 2026

Status: local deferred-capture/USB prototype plus authorized pending-batch backend
preview/import. Identity reconciliation and percentage reporting remain pending.

21 October runtime update: the normal SH1106 build now includes both immediate
local matching and deferred capture, with mode confirmation and start/stop on
the device. A separate attendance firmware upload is no longer required. See
[unified terminal operation](../hardware/fingerprint-diagnostic/UNIFIED-ATTENDANCE.md).
This does not complete enrollment upload, timing/identity reconciliation or
student/class attendance promotion. Both options and the feedback contract are
described in report Chapter Three and Appendix B.

21 October clarification: first-time student registration requires automatic
scanner → laptop → backend enrollment transfer and a committed student binding.
The SH1106 local match-first demonstration is not the final application flow.
See [registration and attendance alignment](fingerprint-registration-and-attendance-alignment.md)
for the current gaps and the recommendation to start new attendance batches
without erasing students' enrolled references.

## Confirmed decisions

- Attendance captures fingerprints offline, without loading a gallery per class.

- Match captured probes later; do not mark present merely because capture succeeded.

- Course/session rosters remain HOD-confirmed and snapshot for each class meeting.

- Course/date attendance displays matric identifiers, while database relationships

  retain Student UUIDs. Existing UTME identifiers remain supported.

- Warning threshold initially 75%, configurable; formally excused classes are

  excluded from the denominator. Exactly 75% meets the threshold.

- User reports enrolled-template export, restore and fresh matching have passed

  on the physical scanner. Export and later comparison of a single fresh capture

  was separately validated with positive and negative saved-probe controls on
  16 October 2026; see the physical test notes below.

- Keep the payload and firmware minimal. Result-importer integration is deferred.

## Existing components and gaps

Django attendance supports manual entries, roster approval, course assignments,

class sessions, deduplication, correction history and private student records.

It now ingests ESP32 JSONL snapshots as restricted pending probe evidence.

See [attendance-pending-batches.md](attendance-pending-batches.md). Enrollment
bindings, identity resolution, filtered galleries and percentages remain pending.

The workspace diagnostic terminal has local attendance.csv storage and a serial

export routine. That mode matches enrolled templates FIRST and logs a stored

reference-template hash; it is not the chosen deferred-identification workflow.

Its daily template-hash deduplication must not be reused for per-class attendance.

Opaque template transfer tools exist but are not a production biometric database.

## Minimal deferred-capture flow

1. Authorized staff selects a backend-created class meeting. Provision only its

   UUID and capture settings to the device; no student gallery is needed to capture.

2. AS608 captures and generates a volatile feature probe. Export it through UART

   into ESP32 file storage without enrolling it into a persistent sensor slot.

3. Persist and read back each bounded record before showing CAPTURE SAVED / PENDING

   MATCH. Require finger lift before another capture. Reject malformed/failed

   feature extraction and stop clearly when ESP32 storage is full.

4. Download over the existing USB serial connection with a framed export protocol;

   a COM port is not automatically a removable USB drive.

5. Backend import previews and validates the complete file before accepting its

   batch. Keep original capture times distinct from receipt times. Enforce exact

   event retry handling; changed payloads under an existing event UUID are errors.

6. Store probes as pending evidence; run the compatible matcher, then review

   unknown/ambiguous/out-of-roster outcomes. Only resolved, eligible identities

   produce attendance records. Deduplicate matched students per class meeting.

7. Send a durable import acknowledgement. Never delete the only copy of pending

   evidence automatically; retain device files until successful receipt and the

   agreed retention policy permit deletion.

Versioned JSON Lines is a straightforward initial interchange (Base64 bytes),

with common fields in one header rather than repeated in every scan. A binary

format can follow measured storage/transfer needs; do not optimize blindly.

Header: schema_version, batch_uuid, device_uuid, class_session_uuid,

probe_format, compatibility_group, clock/timezone metadata.

Record: event_uuid, captured_at, probe_base64. Include a final record count and

file digest for integrity. Derive decoded lengths/checksums during import rather

than adding redundant per-record fields. Digests do not authenticate a device;

operator/device authentication and authorization remain separate requirements.

No matric number, slot or match score is available for an unidentified capture.

## Matching feasibility

The exported AS608 representation is opaque, not a generic feature vector or

standard ISO/ANSI template. A compatible software matcher is not implemented.

First verify: capture once -> export probe -> reload later -> compare against

known reference -> test both same finger and different fingers. The laptop may

orchestrate the connected scanner as matcher if supported, but that is distinct

from a software-only laptop matcher and needs explicit prototype validation.

Enrollment-model portability does not by itself prove probe comparability.

Do not auto-promote a capture hash or scanner slot to student identity.

## Course attendance metrics

After a class is closed AND its pending capture batch is reconciled, use the

session's roster snapshot for eligibility. Cancelled classes are excluded.

Formally excused outcomes are excluded from that student's denominator.

percentage = 100 * present / (eligible_completed_classes - excused_classes).

No denominator means no percentage or low-attendance warning. Compare the

unrounded ratio to the threshold. Unreconciled classes produce a visible pending

state; do not treat their uploads as missing attendance and send false warnings.

Late/excused correction permission, cancellation and reporting still need code.

No automatic exam ban or guardian broadcast is implied by a warning threshold.

## Real-time exams/tests: filtered gallery deployment

Export authorized level/course filters through reviewed eligibility lists, binding

student UUIDs and matric identifiers to compatible active enrollment templates.

Use a manifest with package UUID, roster revision, template UUIDs/digests and

scanner/gallery/slot bindings. Do not export raw biometrics with ordinary profile

CSV permissions. Biometric export needs an explicit restricted authority.

The 150-template working limit is a configurable ceiling, bounded by the actual

scanner-reported capacity (the purchased specification is 162). It limits enrolled

reference templates, not ESP32 attendance logs. Two fingers per student consume

two slots. Unknown attendance probes belong in ESP32 storage, not sensor slots.

Warn near the ceiling, but never automatically erase a gallery at 150 scans.

Before replacement: stop identification, verify recoverable enrollment backups

and package compatibility, confirm the new gallery, load/verify each template,

update binding generation and resume only after a verified ready state. Preserve

attendance/capture files. Power-loss recovery must reconcile pending writes;

never assume a partly written gallery or restore receipt succeeded.

For cohorts exceeding capacity, prefer declared examination groups or claimed

matric identity followed by 1:1 verification where supported. A scanner holding

150 references cannot identify an arbitrary member of a larger cohort. Rotating

reference batches may help later processing but does not merge sensor libraries

into an unlimited simultaneous gallery.

## Saved-probe experiment tooling — 16 October 2026

Firmware q (capture), j (Search control), k (direct comparison), and
probe_experiment.py implement single-probe export and later AS608-assisted
comparison. On 16 October 2026, both 1536-byte saved probes were compared against
slot 1 after an operator-reported power cycle, without fresh captures: positive
MATCH (raw score 41), negative NO_MATCH. Inventory stayed [1], capacity 150.
See ../hardware/fingerprint-diagnostic/PROBE-EXPERIMENT.md.

Persistent ESP32 capture files and USB batch download now have an isolated
prototype in hardware/fingerprint-diagnostic/DEFERRED-CAPTURE.md. Student
reconciliation and attendance percentages remain to implement. These controls
do not establish software-only laptop matching, cross-sensor compatibility or
population accuracy.


## Deferred capture prototype - 16 October 2026

The esp32-deferred build saves one unidentified probe per finger presentation,
requires lift between attempts and preserves committed files across reboot.
It stores a shared class/batch/scanner header and compact event records with
UUID, boot UUID and elapsed milliseconds. No calendar timestamp is invented.
USB download validates per-block CRC32, complete stream SHA-256 and local
JSONL readback. It preserves device files and marks interrupted staging writes.
This is a local prototype without device authentication. Authorized pending
backend import now exists; it does not mark attendance or resolve identities.
See ../hardware/fingerprint-diagnostic/DEFERRED-CAPTURE.md for commands,
format limits, initialization safeguards and remaining physical tests.
