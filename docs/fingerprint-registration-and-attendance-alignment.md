# Student fingerprint registration and attendance alignment — 21 October 2026

## Requirement clarified by the user

First-time student registration must include an immediate fingerprint transfer:
scanner → ESP32 → USB-connected laptop → website backend → database, bound to
that student's existing Student UUID. A standalone enrollment in sensor flash or
a manually exported JSON file does not complete this registration requirement.

The user clarified that "delete previous scans" means students' enrolled
fingerprints in scanner flash, rather than previous attendance captures or lists.
Whether to automate such deletion was a design question, not authorization to
erase the scanner or to discard pending registrations.

## Current implementation and mismatch

- `hardware/fingerprint-diagnostic/src/main.cpp` and `attendance_terminal.h`
  implement enrollment and a local match-first check-in demonstration. The
  default SH1106 profile runs this demonstration; it depends on stored scanner
  references and logs by template hash/local calendar date.
- `tools/portable_template.py` exports enrolled templates over USB to private
  laptop JSON, optionally bound to a Student UUID. It does not perform website
  registration or an automatic HTTP enrollment upload.
- A persistent student-enrollment model, enrollment API and the registration
  page/laptop bridge integration are not implemented in the current Django app.
- `esp32-deferred` captures unidentified probes without writing reference slots.
  Its separate backend API imports pending evidence and durable receipts, but
  enrollment binding and identity reconciliation remain unfinished.

The current local terminal is not the final deferred-identification workflow in
[attendance-device-workflow.md](attendance-device-workflow.md). Its daily
duplicate rule must not become the per-class attendance rule. Fixing the OLED
does not close these application integration gaps.

## Proposed enrollment interaction

1. Authorized staff creates/selects the student on the website, which establishes
   the Student UUID and an enrollment request bound to that student.
2. The laptop bridge commands the connected ESP32/scanner to collect enrollment
   presentations and build an enrollment template, with progress visible to staff.
3. Export the complete template automatically to the laptop, validate the bytes
   and send them with the enrollment request to Django immediately.
4. Django validates the request and stores the template and its student binding
   in a restricted biometric subsystem. Slot numbers are deployment details;
   template hashes verify exact bytes rather than identify people.
5. Show registration success only after the database commit returns a durable
   receipt. On failure, show pending/failed synchronization and preserve a
   recoverable copy for retry; do not silently claim completion or erase it.

The scanner, laptop and database cannot share one atomic transaction. Requests
and retries need stable identifiers and reconciliation after interrupted saves.
AS608 payloads remain opaque; storing a template does not supply a compatible
software matcher. Current scanner-assisted matching evidence is described in
[attendance-device-handoff.md](attendance-device-handoff.md).

## Recommended attendance start and cleanup behavior

Confirming **Take attendance** should select/create the class meeting, open a new
capture batch and reset that session's live counters. It should preserve student
enrollments and previous attendance records. Deduplicate resolved attendance by
Student UUID and class-session UUID, allowing the same student in later classes.

For the selected offline deferred workflow, new attendance probes are read from
volatile scanner buffers and saved on ESP32 storage; they are not enrolled into
scanner reference slots. Thus attendance does not require a sensor-library wipe
or a gallery loaded for each class. Reference enrollments may remain unused.

If scanner flash is used only as enrollment staging and later needs space,
automated cleanup can be a separate receipt-gated operation for verified synced
staging slots. A user's confirmation to start attendance alone is not evidence
that every old enrollment reached the database. Preserve templates needed by any
active identification/exam gallery and retain recoverable backups before a
deliberate gallery replacement.

## Next implementation boundary

Implement the enrollment-to-student backend, immediate USB/laptop upload bridge
and website status first, then connect class-session capture and reconciliation
to the SH1106 interface. Keep enrollment, attendance capture and explicit gallery
maintenance as distinct operations in that interface. No firmware, scanner
library, capture files or database rows were changed by this design clarification.
