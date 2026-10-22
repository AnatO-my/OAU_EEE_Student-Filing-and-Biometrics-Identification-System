# Validation — 14 October 2026

## Host checks

All four C++ suites compiled with GCC using `-std=c++11 -Wall -Wextra -Werror` and
completed successfully:

- `tests/protocol_test.cpp`: fixed packet fixtures for command encoding,
  parameters, 115200-baud arithmetic, template count, password error ACK,
  truncation, bounds, header/address/type rejection and checksum rejection.
- `tests/firmware_test.cpp`: the actual `src/main.cpp` compiled against a fake
  Arduino UART/clock. Simulation checked 115200-baud discovery, GPIO16/17,
  startup noise, decoded reports, console re-query, stale-value suppression
  after a corrupt parameter ACK, independent count reads, stopping on an
  incorrect password, and a bounded timeout scan. The capture/match update also
  checked capture-only mode, no-finger polling, full 150-slot search with nine
  occupied entries, feature extraction, synthetic match ID/score, no-match,
  messy-image errors, checksum rejection, malformed results, out-of-range IDs,
  empty libraries, cancellation and distinct operation/finger-wait timeouts.
- `tests/enrollment_test.cpp`: synthetic confirmed erase/count verification,
  fresh-library enrollment in ID 1, two separate scans into buffers 1 and 2,
  model merging, selection of a free slot in a nonempty library, rechecking an
  occupied slot before saving, damaged occupancy-table rejection, mismatch and
  flash-write failures, finger-removal timeout, cancelled enrollment, and
  cancellation of wrong/oversized/missing erase confirmation.
- `tests/template_transfer_test.cpp`: fixed final-data and CRC32 fixtures;
  synthetic export/restore with 32/64/128/256-byte data packets and partial final
  packets; exact 2048-byte limit; empty/out-of-range slot rejection; numeric
  overflow/invalid commands; wrong address/type/checksum; truncated/missing-final
  and oversized transfers; import CRC/readback failure before Store; changed-slot
  guard; failed Store and failed readback after Store; invalid leftover console
  data suppression and bounded input timeout. No biometric samples were used.
- `tests/test_portable_template.py`: nine Python unittest cases passed for JSON
  round trips, UUID preservation, file/field bounds, corrupt exports, byte
  integrity, restore handshakes/receipts, durable pending metadata on failure,
  and refusal of a mismatched declared compatibility group before connection.
  PlatformIO's Python environment has pyserial 3.5; no extra sensor library is
  required.

`git diff --check` passed. The new diagnostic text files were also checked for
trailing whitespace.

## Supplied schematic inspection

The `.pdsprj` ZIP archive was inspected, including component/property strings
in `ROOT.DSN`. Those identify `ESP32-S3-DEVKITC-1` and the fingerprint block as
`VIRTUAL TERMINAL`, with `MODDLL=VTERM.DLL`. The library default is
`BAUDRATE=9600`, while the placed fingerprint terminal's instance properties
have `BAUDRATE=115200`. The project was not opened in Proteus, and a verified
connection netlist was not extracted.
GPIO16/17 are configurable defaults based on the photograph. The virtual
terminal cannot itself report specifications of a physical AS608.

## ESP32 builds

The `esp32-s3` build passed with PlatformIO Core 6.2.0,
`espressif32@6.12.0` and Arduino-ESP32 2.0.17. It produced `firmware.bin` for
ESP32-S3-DevKitC-1-N8, using 18,512 bytes of RAM and 267,509 bytes of application
flash for the initial metadata diagnostic. The capture/match build also passed,
using 18,512 bytes RAM and 269,805 bytes application flash. No project-source
warnings were reported.
The enrollment/erase build passed too: 18,512 bytes RAM and 273,365 bytes flash.

The conventional `esp32` / `esp32dev` profile also passed with the same platform
and Arduino framework versions. It produced `firmware.bin`, using 21,544 bytes
of RAM and 271,117 bytes of application flash. No project-source warnings were
reported. The capture/match build also passed, using 21,544 bytes RAM and
273,405 bytes application flash. The combined PlatformIO command completed with exit code 0 and
`2 succeeded`:

```powershell
pio run -e esp32-s3 -e esp32
```

The enrollment/erase update also passed for `esp32`: 21,544 bytes RAM and
276,933 bytes application flash. Both environments completed successfully.

The portable-template update passed in both environments with the same pinned
toolchain/framework, producing firmware binaries without flashing hardware:

| Environment | RAM | Application flash |
| --- | ---: | ---: |
| `esp32` | 27,704 bytes | 280,817 bytes |
| `esp32-s3` | 24,672 bytes | 277,329 bytes |

The combined build exited successfully with `2 succeeded`; no project-source
warnings were reported. The new arrays hold bounded temporary template data.

## Physical hardware

The user confirmed the physical board is a regular ESP32, so `default_envs`
was changed to `esp32`. Windows enumeration detected a connected CP2102 USB to
UART Bridge Controller (`USB\\VID_10C4&PID_EA60`) initially reporting problem
code 28. After the user installed the driver, PlatformIO enumerated the bridge
successfully on COM12.

The user then supplied a serial-console report from the physical ESP32 and
scanner. This initial report is user-reported hardware evidence; the assistant
had not uploaded firmware or operated the scanner at that point. It confirms a successful EF01 UART
parameter/count read with these module-reported values:

| Field | Reported value |
| --- | --- |
| ESP32 UART pins | RX GPIO16, TX GPIO17 |
| UART format | 8N1 |
| Working and reported scanner baud | 57600 |
| Status register | 0x0000 |
| System ID | 0x0000 |
| Template capacity | 150 |
| Security level | 3 |
| Device address | 0xFFFFFFFF |
| Data packet size | 128 bytes (code 2) |
| Stored templates | 9 |
| Free template slots | 141 |

The console remains at 115200 baud. Model identity remains user supplied as
AS608. Capture and matching are now available through `c` and `m`; their
physical-hardware results remain pending. These operations use volatile image
and character buffers and search the existing template library. Enrollment (`e`)
and confirmed full-library erasure (`d`, then `ERASE` and Enter) are now
implemented and tested in simulation; the assistant has not erased or enrolled
any physical templates. Template export (`t <ID>`) and Python-driven restore are
now implemented and tested with synthetic data. The subsequent physical upload
and slot-10 export passed: the actual exported payload was 1536 bytes, with
length/CRC validation on transfer and SHA-256 validation of the saved record.
Physical restore to slot 11 and an independent export from that slot subsequently
passed: all 1536 bytes, SHA-256 and record UUIDs matched. Its first live scan
acquired an image but returned no match. Cross-module and server-matcher
compatibility remain unverified. No database endpoint, persistent
ESP32 cache or live biometric database write has been implemented.
Supply voltage/current, image dimensions, DPI,
and firmware version remain unverified. The README
example numbers remain explicitly illustrative, rather than this hardware log.

The [hardware transfer test log](../../docs/fingerprint-hardware-test-log.md),
updated 15 October 2026, records the upload/export evidence and remaining checks.

## Selected-slot recognition test — 15 October 2026

The `v <ID>` command validates an occupied target slot, captures a new finger
presentation and issues Search with that start slot and a count of exactly one.
It rejects a returned ID that differs from the requested target. This allows
testing a restored copy while preserving the original enrollment.

The synthetic transfer suite passed with added checks for the single-slot
request, accepted and rejected captures, wrong returned IDs and empty slots.
The regular ESP32 build passed, using 27,704 bytes RAM and 281,737 bytes
application flash before the subsequent physical upload/test below.

The selected-slot firmware was subsequently uploaded successfully on COM12.
The saved 1536-byte slot-10 record passed offline integrity validation again.
The first physical restore attempt stopped in the console handshake before
sending any template data; its pending receipt contains no selected slot.
The Python line reader now accumulates partial reads until newline or its
existing bounded deadline. Ten Python tests passed, including fragmented-line
assembly and oversized-line rejection.

Read-only diagnostics then found the ESP32 responsive but the scanner unavailable:
ReadSysPara/TemplateNum timed out, followed by timeouts across the full baud probe.
After power/UART reseating, authentication and parameter reads recovered at
57600 baud with ten stored templates. Restore to slot 11 and independent export
comparison then passed. A fresh capture against slot 11 returned Search status
0x09 (no match). The diagnostic was corrected to accept both status-only and
five-byte no-match ACKs; the corresponding synthetic checks and regular ESP32
build passed (27,704 bytes RAM, 281,817 bytes flash), and that build was uploaded.

At the user's request, a fresh enrollment was then attempted. It timed out before
detecting the first finger, with no model generated or new slot saved. A new
enrollment and its baseline/restore recognition checks remain pending.

## Guided export menu — 15 October 2026

Added validated occupied-slot listing (`l`), slot selection (`t`), raw export-all
(`t ALL`), and per-step transfer feedback. The companion `menu` command lists
slots, accepts one/several IDs or ALL, writes separate records into a new private
batch folder, reopens and validates each saved file, and writes a manifest with
verified/failed/unattempted slots. The direct CLI also supports `export --all`.

New record schema 2 permits unassigned student identity; schema 1 remains
readable/restorable. Exact byte duplicates retain UUIDs through the private
export profile. No automatic student identity is assigned to a bulk collection.

All four C++ host suites passed. New synthetic checks cover sparse slot tables
across pages, empty libraries, count/index disagreement, selection prompts,
export-all success/failure and per-slot progress. All 20 Python tests passed,
including menu interaction, exact occupied-slot selection, batch file/manifest
validation, stable UUIDs, unassigned/legacy records, corrupted transfers and
simulated disk failure without false success feedback. Terminal feedback does
not include template payloads.

Both PlatformIO builds passed without project-source warnings:

| Environment | RAM | Application flash |
| --- | ---: | ---: |
| `esp32` | 35,896 bytes | 283,693 bytes |
| `esp32-s3` | 32,864 bytes | 280,221 bytes |

The latest menu/listing update has not been flashed or run against physical
templates by the assistant. The user is operating the device through their own
terminal. [EXPORTING.md](EXPORTING.md) gives the required upload/menu commands.

## Full erasure/restoration hardware test — 15 October 2026

After the user exported their current library, the assistant found one occupied
slot (ID 1) and a completed single-template backup. Before erasure, the saved
record/manifest passed validation, a fresh export matched every one of its 1536
bytes, and a second slot list confirmed complete backup coverage.

The explicitly requested Empty operation completed with a zero count. An
independent slot list confirmed the empty library. The saved template was then
restored into slot 1, verified through flash readback, exported independently and
compared with the original backup. All 1536 bytes and SHA-256 matched. The final
library contained exactly slot 1. Template UUID was preserved; a new gallery UUID
was recorded in the private journal/export profile after full erasure.

This is physical hardware evidence for erasure, restoration and byte integrity.
A fresh finger match after this full-erasure test is still pending the user's
terminal check. See the [hardware test log](../../docs/fingerprint-hardware-test-log.md)
for the distinction from the earlier slot-10 copy-only experiment.

## Physical terminal proposal integration — 15 October 2026

Ported the supplied MicroPython behavior into the existing C++ firmware, with
shared scanner/transfer code, three-scan button enrollment, confirmed single-finger
deletion, a continuous erase hold, menu/clock controls, optional SSD1306 output and
DS1307 checks. Local CSV check-ins use template SHA-256 rather than treating a
reusable slot as a person. Persistent changes and log writes require confirmation;
erase preserves check-in history. See [TERMINAL.md](TERMINAL.md).

All six C++ suites pass under `-std=c++11 -Wall -Wextra -Werror`, including the four
existing diagnostic/transfer suites. The two added suites cover:

- Debounce/bounce, startup and held-key suppression, millis wraparound, immediate
  erase-release detection, DS1307 stopped/invalid BCD/date/12-hour cases, leap dates,
  calendar round trips, log identity/date lookup, slot reuse, invalid headers,
  incomplete records and oversized lines.
- The actual terminal controller with synthetic UART replies: three presentations
  into buffers 1/2/2, mandatory lifting, duplicate rejection over all 150 slots,
  slot-zero fallback, full library, changed slot before Store, third-scan mismatch,
  failed Store, cancellation, corrupt ACK, capture error, fresh DELETE confirmation
  and timeout, short/full/cancelled erase holds, history retention, absent RTC,
  failed/successful/duplicate log feedback, removal gating, no scanning on menu
  pages, offline menu access, clock-save failure/success, maintenance pause,
  unchanged template export framing and explicitly confirmed storage formatting.

The Python backup/restore tests still pass: **20 unittest cases**. The reusable
PowerShell runner is `tools/check_host.ps1`; it takes an optional `-Compiler`
argument and defaults to the locally installed Strawberry GCC. These checks use
synthetic data and hardware adapters, not private fingerprints.

Both final PlatformIO builds pass with the existing pinned platform/framework,
without project-source warnings:

| Environment | RAM | Application flash |
| --- | ---: | ---: |
| `esp32` | 40,840 bytes | 397,881 bytes |
| `esp32-s3` | 38,240 bytes | 403,321 bytes |

The assistant did not upload this integration or operate the physical scanner
for it. The user confirmed that the display and DS1307 are not connected yet.
Physical buttons, peripheral timing/electrical compatibility, the third scan
against the merged model, real LittleFS/NVS persistence, power interruption and
actual check-in behavior remain assembly/bench checks. Existing physical template
transfer evidence above remains separate from these simulated UI results.

## Separate accuracy-test firmware — 15 October 2026

Added two standalone regular-ESP32 environments: `esp32-accuracy-identify` searches
the complete reported gallery; `esp32-accuracy-verify` searches one claimed slot.
The original `esp32` environment remains the default and uses only `src/main.cpp`.
Shared UART/query/probe/count/index functions were moved, without changing their
bodies, into `include/scanner_driver.h`. Both sketches continue using the same
packet validation, explicit UART1 pins and timeouts.

Each accuracy experiment separates genuine/impostor and automatic/manual counters,
records TP/FP/FN/TN, unclassified attempts, acquisition/communication/sensor errors,
and pre-presentation polling errors. It requires no per-result input in automatic
mode. A 2000 ms cooldown and observed finger removal precede another presentation.
The 1:N expected ID labels ground truth without limiting the search; wrong IDs
count FN with a separate diagnostic. The 1:1 target must be occupied and returned
IDs must obey the requested range. No template/security/attendance writes occur.

All **nine C++ suite/variant runs** passed under `-std=c++11 -Wall -Wextra -Werror`:
the existing six suites, the accuracy statistics/gate suite, and the actual
accuracy firmware compiled for both test variants. New simulations cover all four
confusion outcomes, wrong identity, no-finger polling, capture/feature failures,
checksum/length/ID failures, communication timeout, two-second and held-finger
gates, genuine/impostor block transitions, settings/occupancy changes, target
validation including slot zero, manual counter mappings, physical debounce,
automatic/manual separation, paused/reset operation and undefined rates.

All **28 Python unittest cases** passed: the existing 20 portable-template cases
plus eight accuracy-recorder cases. The latter cover fragmented records,
header/schema checks, summary arithmetic/rates, count flags, separate sources,
damaged/oversized data, overwrite refusal and the actual CSV emitted by **both**
native firmware simulations passing through the Python recorder. The transcript
fixtures and all other test data are synthetic.

The final PlatformIO run completed with four successful builds and no
project-source warnings:

| Environment | RAM | Application flash |
| --- | ---: | ---: |
| `esp32` | 40,840 bytes | 397,881 bytes |
| `esp32-s3` | 38,240 bytes | 403,325 bytes |
| `esp32-accuracy-identify` | 30,232 bytes | 282,081 bytes |
| `esp32-accuracy-verify` | 30,232 bytes | 282,069 bytes |

The private CSV recorder uses the already installed pyserial and validates the
firmware schema before enabling keyboard forwarding. Its CLI help was checked;
real COM12 capture, physical button timing and actual biometric error rates are
not yet measured. These accuracy builds have not been uploaded by the assistant,
and no scanner/attendance data was modified. See [ACCURACY.md](ACCURACY.md) for
the test procedure, definitions, evidence files and experimental limitations.

## Recorder shutdown correction and user-run evidence — 15 October 2026

The user supplied a terminal transcript showing successful upload of the 1:N
accuracy build and a completed recorder handshake on COM12. That run remained
paused with zero attempts; it does not contain an accuracy measurement. Repeated
Ctrl+C interrupted the recorder's fixed shutdown read window after summary rows
had arrived. Cleanup now temporarily ignores further SIGINT, returns immediately
after the six final summary rows, retains a three-second maximum wait, and
reports incomplete final replies. The previous signal handler is restored.

All 31 Python tests pass, including three new shutdown regressions for completed
replies/signal suppression, timeout/error retention and handler restoration, and
stopping before the firmware handshake. The existing two simulated C++ firmware
CSV round trips still pass through the recorder. Firmware was unchanged by this
Python-only correction; no rebuild/upload was performed for it.

The same supplied transcript then shows the normal diagnostic firmware running
with four occupied slots (1–4). Two fresh capture/extraction/search sequences
returned ID 2. This provides a candidate genuine-finger reference for starting
the 1:N experiment; the operator must use the finger presented in those scans.
Observed optional attendance-filesystem/RTC errors are separate from scanner
matching and are not resolved or erased as part of this accuracy preparation.

## Capture completeness correction — 15 October 2026

A subsequent private run reported 43 genuine-labeled attempts against expected
slot 2: 41 returned slot 2 and two returned slot 1. The operator confirmed that
fingers were switched during that block. The displayed percentage is therefore
not a valid genuine-only biometric accuracy estimate.

The saved CSV contained 42 trial rows. Replaying the raw console confirmed a
corrupted non-ASCII/truncated record for event 18 and an incomplete final summary
response. Its leftover temporary snapshot did not establish a cause; the operator
said the CSV was not open in Excel. Original evidence is retained with a private
`review.md`; no missing trial or final combined total was fabricated.

The PC recorder now reports sequence gaps/non-ASCII data, rejects duplicate IDs,
compares reported attempts with the saved trial count, and publishes a summary
only after all six rows and their combined/case arithmetic validate. Interrupted
responses preserve the previous complete snapshot. Temporary access-denied
snapshot replacement no longer stops trial/history recording and is retried.
Shutdown waits for a complete group rather than any six individual rows.

All 36 Python tests passed, including new regressions for partial groups, combined
arithmetic, access-denied replacement/recovery, corrupt prefixes, missing/duplicate
events and attempt-count disagreement. Both actual native C++ firmware CSV
transcripts still pass through the updated recorder. The old private run was
replayed successfully through it and flagged event 18/final summary as expected.
These are Python-only changes; ESP32 firmware was not changed or uploaded.

## Accuracy enrollment and comparison diagnostic — 15 October 2026

Both accuracy builds now accept explicit `e` enrollment: a fresh statistics
session, two guided scans with lift detection/timeouts, whole-gallery duplicate
check, free-slot recheck before Store, count/occupancy verification after Store,
and automatic target selection. Scan blocks and manual tally buttons retain
their previous behavior. No delete/empty command was added. Store failure is
reported as unconfirmed without an automatic retry.

`q` compares full Search, selected Search and LoadChar/Match from one image,
regenerating live features between methods. It neither changes template flash
nor adds accuracy trials. Its raw diagnostic results are saved in console.log.

The nine native C++ suite/variant executions and all 36 Python tests passed.
New native scenarios cover enrollment success, initially empty/full galleries,
duplicate detection, merge failure, occupied-slot race, Store failure without
retry, cancellation and timeout. Diagnostic checks cover comparison ranges,
buffer selection, no statistics contamination, failed reference load,
cancellation and timeout. Unsolicited enrollment/store and all export/delete/
empty commands are rejected by the synthetic scanner.

Both regular ESP32 accuracy environments compiled successfully:

| Environment | RAM bytes | Flash bytes |
| --- | --- | --- |
| esp32-accuracy-identify | 30256 | 285781 |
| esp32-accuracy-verify | 30256 | 285745 |

No upload or physical enrollment was performed by the assistant. Hardware
validation of the new commands remains pending the user's terminal test.

## DS1307 timestamps in accuracy tests — 15 October 2026

Accuracy v3 initializes only I2C for its RTC, without display/filesystem setup.
It reads the existing DS1307 calendar using the shared validated BCD/calendar
codec, with 100 kHz bus rate and 25 ms I2C timeout. `z` reads once, `w` schedules
ten checks, and explicit `k` sets local time and checks readback after publishing
old statistics/starting a fresh session. Startup never writes a clock value.
Missing, stopped, invalid, stalled and backward readings are explicit statuses.

`ACCTIME` emits a time record after each statistical trial/observation/tally,
linked by session/test/event ID. Recorder timestamps.csv adds PC UTC receipt
time and the RTC-minus-PC difference, keeping existing trial/summary schemas
compatible. Unavailable clock values are NA, not invented values. Recorder
close flags trials missing their RTC rows. Explicit --sync-rtc uses PC UTC
and refuses a firmware/PC offset mismatch; default offset is +60 minutes.

All ten native C++ suite/variant executions and all 38 Python tests passed.
Clock regressions cover missing/short I2C replies, CH-stopped/invalid calendar,
stalled/backward readings, set/readback, invalid dates, cancellation, timeout,
ten watch samples and unavailable-time output. Recorder regressions cover
timestamp validation, timezone conversion, missing-row reporting and real
native firmware transcript timestamps for every recorded event in both builds.

Both final builds succeeded without the timestamp buffer warning:

| Environment | RAM bytes | Flash bytes |
| --- | --- | --- |
| esp32-accuracy-identify | 30632 | 334005 |
| esp32-accuracy-verify | 30632 | 333973 |

No physical RTC timing, power-off retention, wiring or accuracy claim has been
verified yet. The user will attach the module and run the documented checks.

## RTC sync startup correction — 15 October 2026

A user-run capture stopped with an apparent UTC-offset mismatch. Its console
had the RTC schema header but no ACCTIME row: reconnecting to running firmware
via `h` reprints headers, not the startup clock reading. The PC recorder compared
the unknown offset (`None`) with +60 and incorrectly reported a mismatch.

The recorder now requests a fresh `z` report when the offset is unknown, waits
up to five seconds for it, then checks the actual reported value before sending
any clock-setting command. An actual mismatch names both values; no reply
reports missing RTC status rather than a timezone error. This is a PC-only fix;
firmware does not need reflashing. New regressions cover unknown/fragmented RTC
reports, unavailable-clock reports still carrying the offset, actual mismatch,
and legacy firmware without RTC commands. All 40 Python tests passed, including
both native firmware CSV round trips. Physical retry remains pending.

## Diagnostic comparison order — 15 October 2026

The user supplied a fresh slot-1 q capture with full Search success, selected
Search 0x09 and direct Match 0x08, each in valid frames. Before interpreting
those outcomes as independent method failures, q now rotates selected/direct/
full, direct/full/selected and full/selected/direct across captures. The armed
message prints the order, and Search diagnostics print start and count. Live
features are regenerated before each comparison; each capture still uses one
image. Statistical scan behavior and template flash are unchanged.

All ten native suite/variant executions and 40 Python tests passed. Native
regressions verify all three exact operation sequences, query ranges, buffer
selection and no added attempts or Store commands. Both updated accuracy
environments compiled successfully: identify RAM 30632/flash 342857 bytes;
verify RAM 30632/flash 342817 bytes. The assistant did not upload firmware.
Physical order-comparison results remain pending.

## Fresh-capture diagnostic correction — 15 October 2026

The user supplied three rotated captures. Each first comparison succeeded:
selected Search, direct Match and full Search respectively. Later comparisons
rejected, and one third feature extraction returned 0x07. Reprocessing one image
cannot be assumed independent on this module; the exact internal cause remains
unverified. This does not explain every older statistical 1:1 failure because
the statistical path already performs only one extraction and Search per image.

q now runs exactly one extraction and one method per fresh capture, cycling
selected Search, direct Match and full Search across requests. Tests simulate
invalidating a reused image and verify complete diagnostics across three fresh
captures, no extra attempts and no Store operations. The usual statistical
capture path is additionally checked for exactly one extraction per trial.

All ten native suite/variant executions and 40 Python tests passed. Both final
builds succeeded: identify RAM 30632/flash 342733 bytes; verify RAM 30632/flash
342693 bytes. No hardware upload was performed by the assistant. The fresh
slot-1 1:1 statistical experiment remains pending.


## Saved-probe experiment � 16 October 2026

Both `esp32` and `esp32-s3` profiles build successfully with the saved-probe
commands. The S3 profile remains the configured N8 profile, not an N16R8-specific
validation. ESP32 application uses 46,992 bytes RAM / 399,605 bytes flash; S3 uses
44,392 bytes RAM / 405,073 bytes flash.

Five C++ suites pass under -std=c++11 -Wall -Wextra -Werror: protocol, firmware,
enrollment, template transfer and probe experiment. The new fixture checks fresh
capture export, saved-byte-only comparison, explicit no-match, corrupt CRC,
readback mismatch, wrong returned slot, empty reference and unauthenticated stop.
Persistent Store operations are absent; comparison issues no GenImg command.
Existing 20 portable-template Python tests and 8 new probe CLI tests pass.
Probe/result JSON files default to ignored private-data/fingerprint-probes.

No firmware upload, serial-port opening, real capture or physical probe comparison
was performed by this work. Hardware execution is paused pending the user's
board/COM verification. See PROBE-EXPERIMENT.md for controlled next steps.


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
