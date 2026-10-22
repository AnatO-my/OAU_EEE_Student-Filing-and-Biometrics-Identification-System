# Single capture, saved file, later matching

Prepared 16 October 2026. Diagnostic experiment, not attendance integration.
Follow-up: regular ESP32 / COM12 verified and firmware uploaded on 16 October 2026.
Fresh-probe physical capture/comparison is still pending scanner reconnection.
No physical pass is claimed by synthetic tests or firmware compilation.

## What this proves

A fresh image is converted once into a volatile AS608 feature probe and exported
to a private laptop file. A later command downloads those bytes into buffer 1,
reads them back exactly, loads the existing reference into buffer 2 and compares
the two buffers directly. The original single-slot Search route is retained as a control.
There is no fresh capture during comparison and no Store/Delete/Empty operation.
The AS608 remains the matcher; this is not software-only laptop matching.
A passing experiment establishes a path for later scanner-assisted processing,
not its throughput, accuracy or production readiness.

## Before hardware execution

Verify the connected board, COM port and unchanged scanner wiring first. The
current esp32-s3 build profile is N8, not an N16R8-specific profile; do not assume
it represents a connected N16R8 module. Upload only the verified profile.
Keep an already enrolled reference finger in an occupied slot. Do not erase or
re-enrol it between tests. Close Serial Monitor before Python opens the COM port.
Existing diagnostic transfer backups can be retained as usual.

Run commands from C:/Users/Ot/Downloads/EEE-Project. After board/port verification,
set these variables (replace COMx and the example slot with verified values):

```powershell
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
$probePort = 'COMx'
$referenceSlot = 1
$probeScannerId = [guid]::NewGuid().ToString()
$probeTool = 'hardware/fingerprint-diagnostic/tools/probe_experiment.py'
```

The scanner UUID is an operator-assigned commissioning label. It does not read a
hardware serial number or authenticate the scanner. Keep its value for both
captures and comparisons. Reuse a known commissioning UUID instead if available.
The first experiment deliberately requires the same scanner and compatibility
label, rather than assuming portability to an untested module.

## Positive control: save the enrolled finger's probe

```powershell
& $fpPython $probeTool capture --port $probePort --scanner-id $probeScannerId --out private-data/fingerprint-probes/same-finger.json
```

Lift the finger first. When the tool says PLACE, present the enrolled reference
finger ONCE. It exports a single feature probe without matching or enrolling it.
Success is a byte-count/CRC-checked transfer plus a saved/read-back JSON file.
The output filename must be new; the tool does not overwrite earlier captures.

Lift the finger and unplug/reconnect the board to discard volatile scanner data.
Wait for startup and confirm its COM port if Windows assigned another number.
Keep all fingers OFF the scanner for the comparison:

```powershell
& $fpPython $probeTool compare --port $probePort --scanner-id $probeScannerId --probe private-data/fingerprint-probes/same-finger.json --slot $referenceSlot --method direct --out private-data/fingerprint-probes/same-result.json
```

Expected: MATCH for the chosen reference slot. The result file records the probe
UUID/hash, target slot, time, MATCH/NO_MATCH and raw unitless score. A score is not
a percentage, and the module uses its configured security level for acceptance.
A NO_MATCH is a valid comparison response, not a transfer pass for this positive
control. Failed transfers/settings mismatches produce no success report.

## Negative control: a different finger against the SAME reference

Capture another finger without enrolling it, then lift it and reconnect again:

```powershell
& $fpPython $probeTool capture --port $probePort --scanner-id $probeScannerId --out private-data/fingerprint-probes/different-finger.json
& $fpPython $probeTool compare --port $probePort --scanner-id $probeScannerId --probe private-data/fingerprint-probes/different-finger.json --slot $referenceSlot --method direct --out private-data/fingerprint-probes/different-result.json
```

Expected: NO_MATCH. Do not point the negative control at that other finger's own
enrolled slot. Repeat comparisons of the same saved files: no finger is needed.
Confirm occupied slots/count remain unchanged using the existing list command.

Do not share the probe JSON or bytes in chat/Git. Files go in ignored private-data.
Report only board/port, probe byte counts, positive/negative results, raw scores,
security level, whether the power cycle was performed, and whether the gallery
count stayed unchanged. These few controls do not establish FAR/FRR statistics.

## Firmware console contract

- q: lift -> fresh capture -> Img2Tz(buffer 1) -> UpChar -> FPPROBE/FPDATA/FPEND.
- j SLOT LENGTH CRC32 (Search control) or k SLOT LENGTH CRC32 (direct comparison): checks that the reference slot is occupied, emits
  FPPROBEREADY with current security/system/address, accepts bounded hex lines,
  validates CRC and exact sensor-buffer readback, then either searches that slot or loads its reference into buffer 2 for Match.
  The CLI defaults to --method direct; --method search selects the original control.
- FPPROBERESULT SLOT MATCH SCORE or FPPROBERESULT SLOT NO_MATCH 0.
- Errors/timeouts/invalid packets stop the operation; they are not NO_MATCH.

Both commands pause the terminal UI. It stays paused after the experiment; send
'a' only when ready to resume the existing terminal. This is not a persistent
ESP32 capture file, batch importer, student identity binding or attendance mark.


## Preliminary physical observations — 16 October 2026

The connected scanner reports capacity 150 and one occupied slot (1). A 1536-byte
probe was saved. After an operator-reported power cycle, reloading it followed by
single-slot Search returned NO_MATCH. A live control matched slot 1 with raw score
198. A subsequent direct buffer comparison of the saved probe matched with raw
score 41; gallery membership remained unchanged. Those scores are not percentages
and different operations need not have identical score scales.

Final direct-mode controls passed after an operator-reported USB power cycle,
without fresh readings: the saved enrolled-finger probe matched slot 1 (raw
score 41); the saved different-finger probe returned NO_MATCH. Both probes were
1536 bytes. Inventory remained [1], capacity 150. The failed first negative
capture attempt was not counted. This demonstrates AS608-assisted saved-probe
1:1 comparison for these controls, not a laptop-only matcher or FAR/FRR.
A no-match response does not provide a measured score; 0 in the console protocol
is a placeholder, normalized to null in new host reports.
