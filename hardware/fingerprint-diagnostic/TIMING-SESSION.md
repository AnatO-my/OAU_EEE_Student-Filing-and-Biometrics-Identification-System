# Hardware timing session staged for 26 October 2026

This is an operator plan, not observed results. Do not add timings to Chapter Four
until the corresponding real run has completed and its metadata has been checked.
The 15 October one-person pilot is separate from the later operator-reported
31-person/310-finger/800-placement experience. These tests do not require enrolling
all those fingers again.

## Before running hardware commands

- Confirm the actual board/build, AS608 identity label, scanner firmware if known,
  USB COM port, USB power, sensor UART settings and physical wiring. Record unknowns.
- Close serial monitors and other programs using the port. Record security level,
  occupied reference count, reported capacity, reference slot, gallery generation,
  batch UUID and class-session UUID where applicable. Do not assume capacity 162
  from advertising when the attached unit reports 150.
- Have a recoverable existing reference backup and known genuine/unenrolled controls.
  Do not erase, format, clear, change security or replace galleries for this test.
  Restore is an optional scanner write to a verified free slot, requiring an
  explicit operator decision; inspect pending receipts after any interruption.
- Keep all payloads, console logs and receipts under ignored `private-data/` on a
  protected laptop, outside the report. Review metadata before sharing. The timing
  harness does not configure Windows ACLs or encrypt files.
- Backend import tests require a separate disposable/scratch backend with its schema
  ready and an authorized course-scoped staff account. No live migration, live
  student data, real email or public upload is part of this staged session.

## Existing accuracy measurements

Use `ACCURACY.md` and `docs/fingerprint-reporting-test-session.md` for the existing
guided genuine/unenrolled recording tool; do not invent another accuracy engine.
Record placements in a separate ledger, including missed presentations, retries,
acquisition errors and communication errors. Keep genuine and unenrolled cases
separate; record expected identity and actual returned identity/result. Do not
interpret raw matching score as a percentage. Predetermine repeat counts before
the run and retain failures rather than retrying until a passing sample is obtained.

Existing firmware `total_ms` starts at the image command and ends at the result;
`search_ms` covers the Search command transaction. Neither is full attendance
throughput. Finger-placement waiting, the 2000 ms cooldown and subsequent RTC read
are excluded. Capture and feature extraction are not separately timed. Record
fresh build/settings if comparing with the 15 October pilot.

## Monotonic transfer and saved-probe timings

The new `tools/timing_session.py` calls existing tools directly, with fixed allowed
operations. It runs nothing on import and accepts no arbitrary executable or shell.
It stores private console output plus `timing-metadata.json` in a fresh run folder.
Arguments, payloads, return values and exception text are excluded from that JSON.
Do not run capture commands inside this harness: an operator's finger wait is not
processing latency. Start/end UTC timestamps are labels, not duration clocks.

| Phase | Measured interval and exclusions |
| --- | --- |
| `receive_batch` | Entry to existing deferred receiver through validated JSONL construction; starts after export command write, excludes port connection and final disk save; includes serial/block transfer, checksum checks and conversion |
| `save_download` | Local temporary write, flush/readback validation and publication; excludes scanner transfer |
| `compare_probe` | Existing saved-probe compare request through validated result; includes protocol handshake, byte upload/pacing, sensor readback and compare; excludes port connect and reading input JSON, so not pure matcher time |
| `save_new` | Existing result JSON save/readback after comparison |
| `receive_export` | Existing enrolled-template response reception/validation; excludes the preceding request/port connection and later JSON file save; not the full export transaction |
| `restore_bytes` | Existing reference restore transaction and verification; includes free-slot checks, upload and byte verification; may include callback receipt writes; excludes port connect, initial JSON read and final receipt publication |
| `process_elapsed_ms` | Host invocation of existing `main()` including parse/port connect and file work; deliberately not called transport or matcher latency |

Each phase logs `completed:false` if it raises. A timed phase succeeding does not
make the whole operation successful; check the top-level `completed` and exit code.
Use phase names exactly when reporting. Do not combine these intervals with RTC
offsets, UI timing, timeout constants or the elapsed time between separately saved
probe and comparison files. Intervals use `perf_counter_ns`, reported in ms.

Open PowerShell in the repository and set verified values (placeholders below are
intentionally not runnable device identifiers):

```powershell
Set-Location -LiteralPath 'C:\Users\Ot\Downloads\EEE-Project'
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
$timer = 'hardware/fingerprint-diagnostic/tools/timing_session.py'
$port = 'REPLACE_WITH_VERIFIED_COM_PORT'
$batch = 'REPLACE_WITH_EXISTING_BATCH_UUID'
$scanner = 'REPLACE_WITH_COMMISSIONED_SCANNER_UUID'
$slot = 1 # Replace with the verified existing reference slot.
$group = 'REPLACE_WITH_TESTED_COMPATIBILITY_GROUP'
```

### Deferred batch download

Follow `LAPTOP-DOWNLOADER.md` to create/collect/stop a batch beforehand. It must be
bound to the intended backend-created meeting; importing cannot silently reassign
it. Capture success means pending evidence, not identified attendance.

```powershell
& $fpPython $timer deferred-download -- download --port $port --batch $batch
```

Repeat the *same stopped batch* into fresh default destinations for transfer
repeatability. Predetermine, for example, three repeats; log capture count and bytes
for each batch and label this a repeated-download experiment. A zero-capture batch
does not measure transfer performance for a populated class. Do not delete the
device's originals after download. Clock/identity review may remain outstanding.

### Saved-probe comparison

Follow `PROBE-EXPERIMENT.md` to obtain distinct known-genuine and known-unenrolled
saved probes. Capture them separately using the existing tool, with the finger
removed before comparison. Power-cycle only when intended by the protocol, record
whether it occurred, verify the reference remains available, then keep fingers off.

```powershell
$probe = 'REPLACE_WITH_PRIVATE_SAVED_PROBE_JSON_PATH'
$result = 'REPLACE_WITH_NEW_PRIVATE_RESULT_JSON_PATH'
& $fpPython $timer probe-compare -- compare --port $port --scanner-id $scanner --compatibility-group $group --probe $probe --slot $slot --method direct --out $result
```

Choose a new result filename for every repeat. Record expected MATCH/NO_MATCH,
actual result and any failure separately from timing. Repeated comparison of the
same saved bytes tests transaction repeatability, not independent placements or
population recognition accuracy. It is AS608-assisted, not laptop-only matching.

### Existing enrolled reference export / optional restore

```powershell
& $fpPython $timer reference-export -- export --port $port --slot $slot
```

Record the saved path printed in the private console, byte count, verified receipt
and source gallery settings. Optional restore requires a chosen compatible saved
reference, verified free capacity, preserved source and a fresh receipt path:

```powershell
$reference = 'REPLACE_WITH_PRIVATE_REFERENCE_FPT_JSON_PATH'
$gallery = 'REPLACE_WITH_CURRENT_GALLERY_UUID'
$receipt = 'REPLACE_WITH_NEW_PRIVATE_RECEIPT_JSON_PATH'
& $fpPython $timer reference-restore -- restore --port $port --record $reference --target-scanner-id $scanner --target-gallery-id $gallery --compatibility-group $group --receipt $receipt
```

Do not automate repeated restores: each may occupy a new reference slot. Inspect
receipts and inventory after each attempt. An interrupted Store can have succeeded
without a receipt; do not blindly retry. No erase command is provided here.

## Backend transport and final reporting

Use the separately staged attendance implementation checklist for scratch-only
preview/import/replay/conflict and finalisation tests. Measure authenticated HTTP
requests using monotonic client boundaries and report network/serialization/server
work together unless separately instrumented. Do not include time typing tokens or
choosing files. A valid pending import is not proof of resolved attendance.

For each operation record planned repeat count, completed count, failures and stage,
phase name, units, all individual durations, median and min/max for comparable runs.
Do not pool empty/populated batches, different counts, settings, modes or genuine
and negative cases. Keep source run folders and a metadata-only evidence ledger.
Leave unperformed sections explicitly pending.

Synthetic harness self-check only (opens no device and reads no real payloads):

```powershell
& $fpPython -m unittest discover -s hardware/fingerprint-diagnostic/tests -p test_timing_session.py
```
