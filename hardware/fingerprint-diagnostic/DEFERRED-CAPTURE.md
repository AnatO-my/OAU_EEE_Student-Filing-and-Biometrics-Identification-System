# Offline capture and USB download

**21 October update:** the normal `esp32-sh1106` firmware now includes this capture
controller and the OLED/button interface together. Provision batches with the
USB commands below, then select Deferred and start on the device; a different
attendance build is no longer required. See [UNIFIED-ATTENDANCE.md](UNIFIED-ATTENDANCE.md).
The selected batch is retained, while capture remains disarmed after reboot.

This prototype stores unidentified AS608 probes on the ESP32. A successful save
means **pending identity match**, not student attendance. It does not enrol,
search, compare, overwrite, or delete any scanner reference template.

The legacy capture-only `esp32-deferred` development profile uses the existing flash
partition layout and LittleFS with automatic formatting disabled. Its legacy
OLED/button attendance mode is disabled so it cannot record template-based
check-ins while unidentified capture is armed. Existing diagnostic q/j/k tests
remain available. Do not select the S3 profile for this ESP32-D0WD board.

For a new board whose filesystem has never been initialized, run
`deferred_batches.py initialize-empty --port COM12` once. This explicitly checks
every byte of the live filesystem partition is erased before creating LittleFS.
An initialized, nonempty, corrupt, or unreadable partition is never formatted by
this command; preserve it for recovery instead.

## Start a class batch

Use a real backend-created attendance class-session UUID when preparing actual
attendance. The scanner UUID and compatibility group are commissioning labels;
the AS608 protocol does not prove which physical scanner is attached. Keep the
same verified unit attached. The firmware creates a stable device UUID in NVS.

```powershell
$fpPython = 'C:/Users/Ot/.platformio/penv/Scripts/python.exe'
$batchTool = 'hardware/fingerprint-diagnostic/tools/deferred_batches.py'
$batch = [guid]::NewGuid().ToString()
$classSession = 'BACKEND_CLASS_SESSION_UUID'
$scannerId = 'COMMISSIONED_SCANNER_UUID'

& $fpPython $batchTool begin --port COM12 --batch $batch --class-session $classSession --scanner-id $scannerId --compatibility-group as608-unit-1
& $fpPython $batchTool arm --port COM12 --batch $batch --watch
```

Lift the finger first, then place it once. After each attempt, lift it completely
before another scan. `--watch` shows saved/retry feedback without printing probe
bytes; Ctrl+C stops capture. Without `--watch`, the command returns after arming
and the ESP32 continues while powered. USB connection type C versus micro does
not change the serial protocol; the current board exposes COM12 via CP210x.

Internet access is unnecessary. A power loss preserves committed captures but
stops capture: reconnect and explicitly arm the same batch to continue. A new
boot UUID separates elapsed times across restarts. Any diagnostic command or new
tool connection stops unattended capture before sharing the scanner UART.

## Download without deleting

```powershell
& $fpPython $batchTool list --port COM12
& $fpPython $batchTool stop --port COM12
& $fpPython $batchTool download --port COM12 --batch $batch --out "private-data/fingerprint-probes/batches/$batch.jsonl"
& $fpPython $batchTool validate "private-data/fingerprint-probes/batches/$batch.jsonl"
```

Use a new output filename for another download. The device retains its files;
downloads never acknowledge database import or authorize deletion. The current
prototype deliberately has no batch deletion command. A batch can be armed
again to append captures; each download is a snapshot. Future import must keep
each event UUID's content immutable and deduplicate resolved students per class.

## Stored format and recovery

The device keeps `/probes/<batch UUID>/header` and numbered capture files.
It writes `pending`, flushes/closes, checks byte-for-byte readback, renames to a
new committed filename, then verifies again before issuing `FPBSAVED`.
Each binary block includes CRC32. No C++ struct padding is serialized.

The 164-byte header contains magic FPB1, device/batch/class/scanner UUIDs,
a zero-padded 80-byte compatibility label (79 characters maximum), AS608 source
parameters, and CRC32. Integers use big-endian byte order.

An event contains magic FPE1, event UUID, boot UUID, 64-bit elapsed milliseconds,
16-bit probe length, probe bytes and CRC32: 50 bytes overhead plus the probe.
A measured 1,536-byte probe therefore uses 1,586 bytes before filesystem overhead.
There is a 2,048-byte probe bound, 512-capture batch bound and 32 KiB free-space
reserve. Actual space may run out earlier; no fingerprint gallery is wiped.
The scanner's 150-reference capacity is unrelated to these saved capture files.

A leftover `pending` file blocks arming. Export can download valid committed
records with `interrupted_write_pending=true`; it excludes the uncommitted file.
Preserve the device for recovery before trying to reuse that batch. Corrupt,
missing or misnumbered committed files fail export. Nothing is silently skipped,
truncated, reformatted, overwritten, or deleted to make a batch appear complete.
Real brownout recovery still needs physical testing; native tests emulate torn
writes and reboot state, not electrical flash failure.

USB export uses bounded `FPBLOCK`/`FPDATA`/`FPEND` frames plus count and SHA-256
of the complete binary stream. The downloader validates these and writes JSONL:
one common header, each event, then count and SHA-256 of the preceding JSONL bytes.
It checks local file readback and refuses existing output paths. Files default
to ignored private-data; do not commit or share biometric captures.

## Remaining integration

The RTC is not wired into this mode. `captured_at` is null; boot UUID and uptime
are evidence, not a calendar date. Reconciliation must explicitly review timing
until trusted clock provisioning/RTC readback is implemented.

There is no device authentication or offline authorization grant. There is no
enrolment-to-student registry, population matcher, attendance marking or warning
calculation in this device layer. CRC/SHA-256 detects corruption, not forgery.
Use this as a local prototype, not a production attendance ingestion endpoint.
The live capture/save/power-cycle/download/direct-comparison path has now passed
on this unit. Authorized backend preview/import of these JSONL files now exists;
see [the pending-batch API](../../docs/attendance-pending-batches.md). Imports
remain pending evidence. Identity/timing review and reconciliation are next;
see ../../docs/attendance-device-handoff.md.


## Connected-device checkpoint

On 16 October 2026 the application-only upload, guarded blank-partition
initialization and empty-batch reset/download checks passed. A live capture
(1536 probe bytes) then survived an operator-reported USB power
cycle and downloaded identically. Saved-byte direct comparison against enrolled
slot 1 returned MATCH with raw score 80 (not a
percentage). No fresh reading was taken during comparison. Scanner inventory
remains slot 1, capacity 150; capture is stopped and all files are retained.
The test class UUID is synthetic; no attendance records were created. These
controls do not establish population accuracy or recovery from power loss
halfway through a write.
