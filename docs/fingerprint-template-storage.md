# Portable fingerprint templates and identity binding

Prepared 14 October 2026. This describes an implemented diagnostic transfer path
and a proposed database integration. No live database has been changed.

Clarification on 21 October: first-time student registration must automatically
transfer the enrollment template through the laptop to the website/backend and
database. The manual export below is a prototype, not that completed integration.
See [registration and attendance alignment](fingerprint-registration-and-attendance-alignment.md).

## Storage responsibilities

The AS608 generates and retains its enrolled biometric templates. The ESP32 can
load a selected template into the scanner's character buffer, receive the bytes
over UART, and forward them as a portable record. In the current diagnostic,
the ESP32 holds bytes temporarily in RAM; a computer saves the JSON record.
There is no persistent ESP32 template cache or Wi-Fi database upload yet.

The compatible protocol's `LoadChar` (0x07), `UpChar` (0x08), `DownChar` (0x09)
and `Store` (0x06) operations support transfer through a character buffer.
Adafruit demonstrates these operations and data packet types 0x02/0x08 in its
[CircuitPython implementation](https://github.com/adafruit/Adafruit_CircuitPython_Fingerprint/blob/main/adafruit_fingerprint.py).
The exact purchased AS608 module still needs the physical round-trip test below.

Transfer portability and matcher interoperability are separate. We label this
representation **`as608-ef01-opaque`**, not ISO/ANSI minutiae. EF01 specifies the
UART envelope; it does not establish the internal template format. Do not assume
that another EF01 scanner or a server matcher can interpret these bytes. A
database can store an opaque blob before it can perform biometric matching.

This preserves the project's intended server-matching architecture as a
compatibility requirement. The current local `m` diagnostic is not a server
matcher. If no compatible server SDK/decoder is available, evaluate a documented
image/template format and matcher before choosing the final acquisition path.
See the existing [architecture review](biometric-repository-review.md).

## What makes a record unique and parameterized

| Field | Role |
| --- | --- |
| `template_id` | UUID for this enrollment template; keep it when moving/restoring the same record |
| `student_id` | Existing Django `Student.student_id` UUID; several templates can belong to one student |
| `finger_label` | Enrollment label such as `right_index`; not an automatically detected anatomical label |
| `template_format`, `schema_version` | Versioned interpretation of the bytes and record structure |
| `compatibility_group` | Operator-assigned label for modules whose compatibility has been tested |
| `byte_length`, `template_sha256` | Exact size and integrity of this exported byte sequence |
| `template_base64` | JSON-safe encoding of the template bytes |
| `source.scanner_id` | Commissioning UUID for the physical scanner instance |
| `source.gallery_id` | UUID for that library generation; replace after a full erase/reset |
| `source.slot_id` | Local slot where this template was exported; a restore can use a different slot |
| `source` settings | Capacity, security level, packet size, system ID, address and known/unknown firmware label |
| `exported_at` | Computer UTC export time; not the original enrollment time |

The companion tool instantiates a `FingerprintTemplateRecord` with these
parameters and serializes it to JSON. Generate a template UUID on its first
export; pass `--template-id` to preserve it for subsequent backups of that same
enrollment. A fresh enrollment is a new record/version.

The UUID identifies the record, not an intrinsically unique fingerprint.
SHA-256 detects exact byte equality or corruption; it does not recognize a
person. New captures of the same finger can produce different representations.
Finger uniqueness/deduplication requires a suitable biometric comparison and an
enrollment policy. Do not use raw bytes, hashes, confidence scores or scanner
slot numbers as student primary keys.

## Proposed database model and lookup

Keep biometric data in a separate subsystem linked to the existing student UUID.
Use a template table with UUID primary key, student foreign key, finger label,
format/version, compatibility group, byte length, SHA-256, binary payload and
active/revoked status. JSON transport uses Base64; PostgreSQL storage can use
`bytea` rather than a Base64 text column.

Keep scanner deployment bindings in a second table with scanner UUID, gallery
UUID, slot ID, template UUID and pending/verified/revoked state. Enforce one
active binding per `(scanner_id, gallery_id, slot_id)`. If the policy allows
only one active enrollment per student's named finger, enforce that separately.
Do not make `student_id` globally unique in the template table: a student can
have more than one enrolled finger.

For a local diagnostic match, look up `(scanner, gallery, returned slot)` to find
the template/student UUID. For the final server-matching design, submit an
independent probe to the compatible matcher, resolve its matched template UUID,
and apply the application's existing access permissions. Downloading a student's
record does not follow merely from receiving a fingerprint slot ID.

The API must validate student existence and enrollment authority, payload bounds,
format support and byte integrity. Use authenticated transport and controlled
biometric storage; the ESP32 receives no database credentials. Base64, CRC and
SHA-256 provide no encryption or sender authentication. The diagnostic's USB
interface is a commissioning tool, not an authenticated production API.

## Implemented transfer behavior

The [guided terminal export menu](../hardware/fingerprint-diagnostic/EXPORTING.md)
now lists occupied slots and supports one, several or all templates, with
per-step feedback and per-file save/readback confirmation. Each batch has a
manifest recording completed, failed and unattempted slots. New schema-2 records
permit an unassigned student (`null`); legacy schema-1 records remain supported.
Bulk export does not assign every fingerprint to the same student. The private
export profile preserves UUIDs for exact byte duplicates in a gallery.

Firmware commands `t <slot>` and `u <length> <crc32>` are driven by
[`portable_template.py`](../hardware/fingerprint-diagnostic/tools/portable_template.py).
No Adafruit library is required. The C++ code validates EF01 header, address,
packet type, length and checksum and requires a final data packet. It accepts
reported chunk sizes 32/64/128/256 and measures actual total bytes, with a
2048-byte implementation limit; it does not assume a 128-byte template merely
because the scanner reports 128-byte packets.

Export reads an occupied slot without erasing it. Restore receives and checks
the complete input, downloads it to a volatile sensor buffer, reads it back,
rechecks a free slot, stores it and loads/reads it back again. Only exact equality
produces a verified storage receipt. Byte equality establishes transfer integrity,
not recognition accuracy. Test a fresh finger presentation with `m` afterward.

The tool saves a pending receipt before restoring and a verified receipt after
success. It records the proposed free slot in the pending receipt before sending
template bytes. Scanner storage and database/file writes are not one atomic transaction.
A timeout or power loss after Store can leave a slot occupied without a verified
binding. Inspect/reconcile it before retrying; retries can create duplicate
templates. Full erasure requires a new gallery UUID and revocation of old
bindings. The diagnostic does not manage gallery UUIDs or reconcile a database
automatically. Keep a record of commissioning IDs and changes.

## Run the first portability experiment

1. Build/upload the updated regular-ESP32 firmware using the
   [diagnostic instructions](../hardware/fingerprint-diagnostic/README.md), then
   enroll with `e`, note the slot, and match with `m`.
2. Close the serial monitor. Use the existing PlatformIO Python, which includes
   `pyserial`. In the diagnostic directory:

   ```powershell
   $fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
   & $fpPython tools/portable_template.py --help
   & $fpPython -c 'import uuid; print(uuid.uuid4())'
   ```

3. Choose a scanner UUID and gallery UUID once and retain them in private notes.
   Use an existing student UUID for an authorized binding, or a synthetic UUID
   for a hardware-only experiment. Replace the placeholder values below:

   ```powershell
   & $fpPython tools/portable_template.py export --port COM12 --slot 1 --student-id STUDENT_UUID --finger right_index --scanner-id SCANNER_UUID --gallery-id GALLERY_UUID --compatibility-group as608-unit-1 --out ../../private-data/fingerprint-templates/enrollment.fpt.json
   ```

4. Inspect metadata without sharing the biometric payload. To test restore on
   the same module, leave the original slot intact and allocate one additional
   free slot:

   ```powershell
   & $fpPython tools/portable_template.py restore --port COM12 --record ../../private-data/fingerprint-templates/enrollment.fpt.json --target-scanner-id SCANNER_UUID --target-gallery-id GALLERY_UUID --compatibility-group as608-unit-1 --receipt ../../private-data/fingerprint-templates/restore.receipt.json
   ```

5. Record the verified receipt and actual byte count. Reopen the monitor and
   use `m` with a new presentation. Searching a gallery containing two copies
   can return either slot. Use `v <restored slot ID>` and a fresh presentation
   to search only the restored slot without erasing the original.
   Exporting the restored slot can also confirm its
   SHA-256 matches the original.
6. Test movement to a second module only after establishing its compatible
   model/firmware and recording a distinct scanner UUID. An equal user-supplied
   compatibility label is a declared test assumption, not automatic detection.

Real JSON exports and receipts belong in ignored `private-data/` outside shared
artifacts. The source ZIP contains code and synthetic tests, not fingerprint
records. Do not paste `FPDATA` or `template_base64` into the report/repository.

## Evidence to add after assembly

Observed hardware progress is recorded in the
[hardware transfer test log](fingerprint-hardware-test-log.md). The first slot-10
export produced 1536 bytes and passed record integrity validation. Restore to
slot 11 and an independent export comparison passed with identical bytes and
record UUIDs. Its first live capture returned no match; the user requested a
fresh enrollment before repeating the experiment. Recognition of a newly enrolled
and restored copy remains to be demonstrated. This does not establish interoperability.

A later complete-library test on 15 October covered the user's then-current
single-template library (slot 1). The backup was compared with live bytes before
erasure; the scanner was verified empty; the saved template was restored to
slot 1 and independently re-exported with all 1536 bytes and SHA-256 unchanged.
Its template UUID was preserved and its gallery namespace renewed. A live-finger
match after this full-erasure test remains pending. See experiment 2 in the log.

Record module/firmware labels, export length/checksum, exact restore result,
old/new slot mapping, independent recognition outcomes, and transfer times if
measured. Report same-module and cross-module tests separately. Server matching
compatibility, database enrollment endpoints, durable ESP32 caching and recovery
automation remain future integration work.

For score interpretation and recognition metrics, use the
[evaluation reference](fingerprint-score-and-evaluation-reference.md).

## Physical terminal integration — 15 October 2026

The supplied button/menu proposal is integrated into the C++ PlatformIO firmware.
Its [terminal reference](../hardware/fingerprint-diagnostic/TERMINAL.md) documents
the preserved controls, DS1307/optional SSD1306 adapters and assembly checks.
Existing portable-template export/restore commands pause the physical UI until
serial `a`, keeping exclusive use of the scanner and console during transfers.

Local check-in CSV rows use event/device UUIDs, a timestamp, the current slot,
template SHA-256 and raw match score. The daily duplicate key is template hash
and local date; a reused slot therefore does not inherit another template's
record. This hash can be joined to the portable JSON's `template_sha256`, but it
identifies particular template bytes, not a student or all enrollments of one
finger. Student binding and authenticated server attendance remain separate
integration work. The ESP32 does not persist a template-byte cache in this change.
Actual clock/display/button operation and durable local log behavior await the
assembled-hardware tests; no new physical recognition result is claimed here.
