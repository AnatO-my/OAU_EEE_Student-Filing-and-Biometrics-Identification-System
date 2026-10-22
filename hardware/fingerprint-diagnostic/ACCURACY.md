# Fingerprint accuracy experiments

Two separate C++ PlatformIO builds measure recognition outcomes rather than
presenting the sensor's raw score as a percentage. Both reuse the tested EF01
UART driver and GPIO16 RX / GPIO17 TX connection. They require only the ESP32,
scanner and USB serial for recognition; adding DS1307 enables calendar-time
checks and per-attempt timestamps. The display remains optional. No Adafruit
library is required. Scan blocks preserve the gallery. The explicit `e` command
can enroll a new finger into an empty slot before a new experiment. Neither
test exports/deletes templates, changes security, or writes attendance/NVS/LittleFS data.

The normal attendance/diagnostic program remains the default `esp32` build. The
accuracy environments select a different source file and a fixed test type:

| Environment | Scanner comparison | Genuine case | Impostor case |
| --- | --- | --- | --- |
| `esp32-accuracy-identify` | 1:N: Search every reported library slot | Present the known enrolled finger; select its expected ID beforehand | Present a finger **not enrolled anywhere** in the library |
| `esp32-accuracy-verify` | 1:1: Search exactly one selected occupied slot | Present the finger enrolled in the claimed slot | Present a **different finger**, either unenrolled or enrolled in another slot |

For 1:N, the expected ID labels ground truth; it does **not** limit the search.
Any enrolled template can be returned. A genuine search returning a wrong ID is
an identification failure, counted as FN and additionally `wrong_id`; it must
not inflate TP. For 1:1 the search range is just the claimed ID. A response with
another ID contradicts the request and is a protocol error.

The 1:N test therefore checks identity correctness as well as library acceptance.
It does not assume that any returned ID is the correct identity. Use one known
reference slot per evaluation finger; duplicate enrollments of the same finger
under different IDs make slot-based ground truth ambiguous.

## Upload either test

Enroll the evaluation fingers with `e` below or with the normal firmware and
note their IDs. Freeze that library for the experiment. Use a verified backup if needed, then
close Serial Monitor or any other program using COM12.

```powershell
cd C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic
$pio = 'C:\Users\Ot\.platformio\penv\Scripts\platformio.exe'
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'

# Test 1: whole-library identification
& $pio run -e esp32-accuracy-identify -t upload --upload-port COM12
```

For the other experiment, close the recorder/monitor, then upload:

```powershell
# Test 2: one claimed template ID
& $pio run -e esp32-accuracy-verify -t upload --upload-port COM12
```

These targets use the regular ESP32 board that is physically connected. A normal
firmware upload preserves the scanner's library and the existing ESP32 data
partitions. No erase-flash or upload-filesystem step is needed.

## Collect a genuine block and an impostor block

Use the recorder instead of Serial Monitor to save the evidence:

```powershell
& $fpPython tools/accuracy_capture.py --port COM12 --new-session
```

`--new-session` intentionally resets **RAM statistics**, then leaves the experiment
paused. It does not modify fingerprints or attendance files. Omit this option to
continue the current counters. The recorder validates the accuracy-firmware
headers before forwarding keyboard input; it refuses a different CSV schema.

When it says `Recorder ready`, type the following. Replace illustrative ID `1`
with the known slot for the evaluation finger:

```text
t 1          [press Enter]
g
```

`t` selects the expected genuine ID / claimed verification ID. `g` declares a
**genuine block once**, not before each scan. Lift any finger already touching
the sensor, then present the registered finger repeatedly. Each completed scan
updates counts automatically. Lift and replace between presentations.

After the block, press `p` to pause, remove the finger, and press `s` for summaries.
Then press `i` once to start the **impostor block**. Use the appropriate negative
finger from the table above. Do not use an already enrolled different finger as
a 1:N negative: the scanner should recognize that finger, so it is not a false
positive test. The selected claimed ID stays fixed in the 1:1 impostor block.

There is a **minimum 2000 ms cooldown after each scan result**, followed by normal
UART polling/processing. No result-entry or confirmation key is needed before
the next scan. Removal can happen during those two seconds and does not add a
second delay. A finger held continuously is not counted repeatedly; the next
presentation must include a detected lift. This avoids treating repeated images
of one stationary placement as independent trials.

The program initially requires a lift when starting/resuming/changing a block,
so a genuine finger held during a change to `i` cannot become an accidental
impostor trial. Switch fingers only after the new `ACCCONFIG` message confirms
the selected case. A command received during a scanner transaction takes effect
after that transaction; the current trial retains its existing case.

Press `s` whenever you want a fresh CSV summary. Press **Ctrl+C** in the recorder
to pause the scanner, request final summaries, drain their replies and close the
port. Run the two firmware tests separately; their CSV `test` fields identify
which experiment produced each result.
Shutdown ends as soon as all six final summary rows arrive, with a maximum
three-second collection window. Repeated Ctrl+C is ignored during this cleanup
so it cannot interrupt saving; incomplete replies are reported explicitly.

For a console without file recording, use this instead, with the same commands:

```powershell
& $pio device monitor -p COM12 -b 115200
```

## Enroll another finger and repeat

Both accuracy builds support `e` after the recorder says **Recorder ready**.
It prints the previous session's summary, starts a fresh RAM statistics session,
and selects a proven empty slot, preferring IDs starting at 1. Lift your finger,
then follow the scan 1 / lift / scan 2 prompts using the same new finger. Each
stage has a 20-second timeout; `p` cancels before saving. Enrollment runs
separately from automatic/manual trials and adds no accuracy attempts. The
physical buttons retain their manual tally roles.

The first scan is searched against the whole gallery. An existing match stops
enrollment and reports the existing ID; it does not create a duplicate. A failed
duplicate check, failed feature extraction or failed two-scan merge also stops.
The entire inventory/settings are rechecked before Store to avoid overwriting an
occupied slot. After Store, the count increase and occupied slot are verified.
A lost/failed Store acknowledgement is reported as unconfirmed and is never
automatically retried. These checks verify the occupied location/count, not an
exact byte readback; use the normal backup/restore tools for that check.

On `ACCENROLL SAVED ID=...`, that ID is automatically selected and scanning stays
paused. Press `a`, then `g` and do the genuine block with that finger; `p`, `s`,
then `i` starts the negative block. Use a different finger satisfying the test's
impostor definition. A formerly unenrolled negative finger becomes enrolled
after `e` succeeds and can no longer serve as a 1:N negative. Keep enrollment
and gallery changes between experiments; old sessions remain in the recorded
CSV/history. To repeat without enrollment, use `n`, then `t <ID>` + Enter.

## Check matching methods with fresh captures

Select an occupied reference with `t <ID>` + Enter, then press `q`. Lift once
and place a finger within 20 seconds. Each q captures a new image, generates
features exactly once and runs exactly one method. Successive q commands cycle
selected-slot Search, direct Match and full-library Search. The armed line
identifies the method. Use the same enrolled finger but lift/re-present for
each new capture. The direct comparison loads the selected stored reference
into buffer 2 and uses Match (`0x03`). The
[AS608 driver implementation](https://www.libdriver.com/docs/as608/driver__as608_8c_source.html)
documents the corresponding Search, LoadChar and Match commands.

Earlier q versions reused one image and generated its features three times.
Hardware trials showed each method could match when first, while subsequent
methods rejected or extraction failed. The exact internal mutation is unknown;
the repeated-processing results are not independent method measurements.
Fresh-capture diagnostics avoid that sequence. Different placements can still
vary in quality; these few diagnostics are functional checks, not statistical
accuracy trials. Normal automatic accuracy scans already perform one feature
extraction and one Search per capture; their behavior has not changed.

The output records transport status, acknowledgement length, scanner code and
returned slot when applicable; it does not export templates or raw matching
scores. `transport=0` means a valid UART frame, not necessarily a match:
interpret the scanner code for that operation. A diagnostic neither increments
accuracy counters nor changes template flash. It pauses on completion/error;
`q` repeats, `p` cancels while waiting, and `g`/`i` starts normal counting again.
Read its results from `console.log`; no diagnostic rows enter `trials.csv`.

## Add and check the DS1307 RTC

Connect with power off. Default regular ESP32 connections are SDA GPIO21,
SCL GPIO22, and common GND. The DS1307 uses I2C address `0x68` at 100 kHz.
Its VCC operating range is 4.5–5.5 V; use the module's appropriate 5 V supply.
**Keep SDA/SCL at 3.3 V on the ESP32 side.** If the module pulls these lines up
to 5 V, use an I2C level shifter or suitable pull-up changes before connecting
them to ESP32 GPIOs. See the
[DS1307 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds1307.pdf)
and [ESP32 electrical limits](https://documentation.espressif.com/esp32_datasheet_en.html).
SQW is not used. No extra RTC library is required.

Upload either updated accuracy environment. To set the clock explicitly from
the PC clock and begin a new test capture:

```powershell
& $fpPython tools/accuracy_capture.py --port COM12 --new-session --sync-rtc
```

The default clock convention is **Africa/Lagos local time, UTC+01:00**. Ensure
the PC clock is correct. Sync converts PC UTC to this convention regardless of
the PC's displayed timezone. `--rtc-offset-minutes` must match the firmware's
`ACCURACY_RTC_UTC_OFFSET_MINUTES` setting (default 60); a mismatch refuses sync.
Look for `ACCRTC SET VERIFIED`, then press `w` for ten checks about one second
apart. `z` reads once. `k YYYY-MM-DDTHH:MM:SS` + Enter sets local time manually;
it publishes existing statistics and starts a new session before clock entry.
Invalid/stopped time is never silently repaired; boot never sets the clock.

Every recorded scan/observation/manual tally emits a separate `ACCTIME` row,
saved in **timestamps.csv**. Join trial timestamps to trials.csv by
`session`, `test`, `event_id`, filtering `scope=trial`. This preserves the
existing trial/summary CSV schemas. `scope=check` rows come from startup or
`z`/`w` and do not add attempts. RTC time is sampled just after result emission,
at recording time, with one-second resolution; it is not presentation-start
time. Processing latency remains measured using ESP32 uptime before this RTC
read, and the two-second scanner cooldown remains in place.

The timestamp file includes RTC local time, explicit UTC offset, RTC status,
ESP32 uptime, host receipt time in UTC, and `rtc_minus_host_seconds` (RTC minus
PC time after timezone conversion). After sync, a small negative difference
is normal due to one-second resolution and serial/PC delay; use roughly two
seconds as an initial functional check, not a precision calibration claim.
The PC clock/receipt delay affect this comparison. A constant offset and a
growing offset have different causes; a ten-second check does not establish
long-term drift accuracy.

Statuses are `ok`, `io_error`, `stopped` (CH bit set), `invalid`, `stalled`
(same calendar second observed for at least 2.5 seconds), or `backward`.
`ok` means a valid running-bit/calendar read, not independently verified
absolute time. I2C/stopped/invalid reads save time as `NA`; stalled/backward
values remain visible with their status. Recognition can continue when the
RTC is unavailable, without changing confusion-matrix classification.
Missing timestamp rows are flagged in recording-issues.log. Old firmware can
still be captured but has no RTC rows; `--sync-rtc` requires updated firmware.

After successful checking, record several fingerprint trials and inspect their
linked timestamps. For battery retention, stop the recorder, remove main power
for a measured interval, reconnect and capture **without `--sync-rtc`**; use
`z`/`w` to check continuity and compare to PC time. Synchronizing on reconnect
would hide a failed retention test. Keep the previous logs for the report.

## Manual tally mode and the three keys

Automatic mode is the default (`a`). In automatic mode, keys `1/2/3` are ignored
for counting so a recorded scan cannot accidentally be counted twice.

For manual tallying, press `m`, select/confirm the correct `g` or `i` block, and
use these keys. The scanner continues showing observations with its two-second
cooldown; those observations have `counted=0`. Only tally keys update the manual
statistics. They do not block, restart or impose another delay on scanning.

| Key | Physical button in this test firmware | Genuine block | Impostor block |
| --- | --- | --- | --- |
| `1` | ENROLL / GPIO25 | Attempts +1; unclassified +1 | Attempts +1; unclassified +1 |
| `2` | DELETE / GPIO26 | Success +1 → TP +1; attempts +1 | Success +1 → TN +1; attempts +1 |
| `3` | MENU / GPIO27 | Failure +1 → FN +1; attempts +1 | Failure +1 → FP +1; attempts +1 |

Here “success” means **the expected behavior**: accepting a genuine finger or
rejecting an impostor. “Failure” means rejecting a genuine finger or accepting
an impostor. Press and release once per manually recorded outcome. Physical
buttons are debounced and do not repeat while held. Serial key repeats are
separate received commands, so do not hold a keyboard tally key down.

`1` records a standalone attempt whose outcome is unknown. It is not a preparatory
press for `2` or `3`: pressing `1` then `2` records **two attempts**, as both keys
add to the attempt count. Unclassified attempts remain visible and outside the
confusion matrix until you correct the source data in a separately documented
analysis; the firmware does not silently turn them into failures.

Manual tallies are independent events, not automatically attached to a previous
scanner observation. The operator must record one outcome per intended trial.
They may also be entered while paused in an already configured block. Keep the
automatic and manual tables separate; do not add them together. The normal
attendance firmware retains its original button roles when uploaded again.

## Counts, errors and rates

Both sources retain separate genuine, impostor and combined summaries:

| Classification | Ground truth | Completed scanner decision |
| --- | --- | --- |
| TP | Genuine | Correct expected identity accepted |
| FN | Genuine | No match, or a wrong identity in the 1:N test |
| TN | Impostor | No match |
| FP | Impostor | A match accepted |

The `wrong_id` count is a **subset of FN** for genuine 1:N trials, not another
attempt. A wrong identity also represents a false association, but this report
keeps that diagnostic separate rather than counting one presentation twice.
The negative-block FP total measures false acceptance/identification for actual
non-mate presentations.

Automatic attempts start when GenImg reports a captured image or image-capture
error `0x03`. A normal no-finger response `0x02` is not a trial. Acquisition/feature
errors, in-trial communication/protocol errors and other scanner errors each add
one attempt to their own error count. They are not silently reclassified as FN
or TN. An error while polling before a presentation is established increments
`poll_errors` only; after three consecutive polling errors scanning pauses.

The automatic program cannot know that a person tried to scan if the device
reports only “no finger.” To evaluate completely undetected placements, use the
manual mode with a predeclared presentation time limit and record that procedure.
Manual end-to-end labels and automatic completed-search labels can have different
denominators, so keep them separate in comparisons.

```text
Completed decisions = TP + FP + FN + TN
Successes            = TP + TN
Failed decisions     = FP + FN
Attempts             = completed decisions + acquisition errors
                       + communication errors + sensor errors + unclassified

Decision accuracy    = (TP + TN) / completed decisions
Precision            = TP / (TP + FP)
Recall / sensitivity = TP / (TP + FN)
Specificity          = TN / (TN + FP)
False-positive rate  = FP / (FP + TN)
False-negative rate  = FN / (FN + TP)
Decision coverage    = completed decisions / attempts
```

All rates are printed as percentages. Zero denominators produce `NA`, not a
misleading zero or 100%. Poll errors are excluded from attempts because no
presentation was established. Always report attempts, completed decisions,
coverage and errors alongside accuracy; a high completed-decision accuracy must
not hide acquisition failures. Overall accuracy also depends on the genuine /
impostor mix, so compare case-specific rates and denominators across setups.

For the 1:N experiment, the negative-block error rate corresponds to an observed
false-positive identification rate and the genuine-block error rate includes
no-match/wrong-identity identification failures. NIST distinguishes searches
with an enrolled mate from searches without one in its
[fingerprint identification metrics](https://fingerprint.nist.gov/frifte/e1n/results/dermalog%2B0003/metrics.html).
This prototype protocol and its summary are not a standards certification.

## Saved evidence

The recorder creates a new folder under ignored private project storage:

```text
private-data/fingerprint-accuracy/run-<UTC-time>-<suffix>/
    console.log             # Full scanner/test configuration and diagnostic output
    trials.csv              # Automatic scans, manual observations and tally events
    summary-history.csv     # Every requested/received summary snapshot
    latest-summary.csv      # Latest complete six-row snapshot per session/test
    recording-issues.log    # Missing/corrupt data and summary publication notices
    timestamps.csv          # RTC checks and trial-linked times plus PC comparison
```

The UTC suffix labels host capture time; processing durations use ESP32 uptime,
and real RTC reads are saved separately in timestamps.csv. Output folders are never overwritten. Use
`--out <new-folder>` to choose another destination. Keep these pseudonymous,
linkable trial logs private; raw fingerprint images/templates are not collected.

`trials.csv` distinguishes `event_type=scan` / `manual_key` and `counted=1` / `0`.
Filter to `counted=1` and the intended test/source/session when calculating counts.
A manual-mode scan observation must not be counted again as a manual key event.
Each row includes the case, expected/returned slot, raw scanner confirmation code
when available, error stage, elapsed time, security level, gallery count, capacity
and uptime. The sensor's raw numeric matching score is not used or exported.

`total_ms` measures the image-command start through the result/error;
`search_ms` measures the Search command through a valid result and is `NA` when
unavailable. The two-second cooldown and human placement waiting are outside
these processing times. Restrict latency analysis to the appropriate completed
outcomes; do not pool failed transactions with successful searches without saying so.

Counters live in **RAM** and reset on reboot. Capture throughout the experiment.
Attaching halfway through can save existing summary totals but cannot recover
earlier trial rows. Without `--new-session`, preexisting counters are intentionally
retained. The recorder validates CSV widths, classification/count flags, summary
arithmetic and percentage denominators; malformed data stops capture and keeps
the raw log. It does not silently accept a damaged result row.
Trial IDs are checked for gaps/duplicates. Non-ASCII data during a trial run and
differences between firmware attempt totals and recorded trial rows are reported
in `recording-issues.log`; missing rows are never invented. Capturing halfway
through a session is also marked as having unavailable earlier trial rows.

The latest snapshot is published only after all six summary rows arrive and each
combined total equals its genuine and impostor totals. An incomplete response
keeps the previous complete snapshot and leaves its received rows in the history.
If replacing the snapshot is temporarily denied, trial/history recording
continues and publication is retried. Review recorder notices before using data
for the report. The cause of any USB/UART corruption requires separate diagnosis.

Keep the same known finger throughout a genuine block with a fixed expected ID.
Pause before switching fingers; select the new expected ID and restart `g` for a
different enrolled finger. Use `i` only with a finger that satisfies that test's
impostor definition. Switching fingers under an unchanged ground-truth label
invalidates the corresponding accuracy estimate even if every scan is recorded.

## Conditions to record before comparing results

Create a private `notes.md` beside each run with the assembly/firmware revision,
scanner label, test type, pseudonymous finger/participant labels and expected IDs,
gallery size, security setting, planned trials per case, and the condition being
changed (placement, dry/wet finger, pressure, etc.). Keep references fixed for a
comparison and change one condition at a time. Use several fingers/participants
and adequate genuine and impostor trials for the claim you want to make.

The firmware checks settings, occupied count and the occupancy bitmap whenever
a block starts/resumes. A change requires a new session (`n`) after saving old
results. It cannot prove that bytes in an occupied slot or a physically swapped
scanner are unchanged; its system ID is not a unique serial number. Keep the
hardware/references controlled. Use a new session after re-enrollment, scanner,
security setting or test-condition changes. Session labels combine a boot nonce
with an in-memory sequence and are also separated by the host capture folder.

Repeated scans of one finger are not population-wide independent observations.
Zero observed errors means `0/n` for this sample, not a proven zero underlying
error probability. Report sample size and uncertainty; see the existing
[score/evaluation reference](../../docs/fingerprint-score-and-evaluation-reference.md).
No single fixed operating point or accepted-only score list establishes an EER
or a full ROC/DET curve. There is no liveness/spoof-resistance test in this program.

## Return to the normal terminal

Close the recorder/monitor and upload the original default environment:

```powershell
& $pio run -e esp32 -t upload --upload-port COM12
```

Its [normal controls](TERMINAL.md), enrollment, attendance UI and existing
portable-template backup/restore functions then become available again.
