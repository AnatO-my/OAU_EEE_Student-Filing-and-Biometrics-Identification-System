# Physical terminal integration — 15 October 2026

**Superseding 21 October update:** both attendance paths now run in the normal
SH1106 build. See [UNIFIED-ATTENDANCE.md](UNIFIED-ATTENDANCE.md) for runtime mode
confirmation, prepared class-batch selection, start/stop and the feedback rules.
The unified application starts stopped. Older six-page/automatic-Home details
below describe the earlier local-only interface.

The supplied MicroPython proposal has been ported into the existing **C++ / Arduino
PlatformIO** firmware. Keep using this project; there is no `main.py` to upload.
The existing EF01 scanner driver, diagnostics, portable JSON backups and verified
restore protocol remain in use. No Adafruit or other extra library is required.
Wire, LittleFS, Preferences and SHA-256 are provided by the pinned ESP32 framework.

The display adapter supports an optional **SSD1306 or SH1106 128×64 I²C OLED** at
`0x3C`; the clock is a **DS1307** at `0x68`. A user photograph on 20 October shows
a powered display with a readable top band and noisy lower pages. The user's
subsequent test confirmed the SH1106 driver works best; it is now the default
attendance build. An absent
display is skipped, USB prints the action prompts, and matching/enrollment/export
still work. Check-in logging requires a running clock and writable local storage.
The UI and scanner logic are separate from the display adapter. A character LCD
is not driven by this version.

## Connections

| Function | Regular ESP32 (current board) | ESP32-S3 profile |
| --- | ---: | ---: |
| Scanner TX → ESP RX | 16 | 16 |
| Scanner RX ← ESP TX | 17 | 17 |
| ENROLL button | 25 | 13 |
| DELETE button | 26 | 14 |
| MENU button | 27 | 15 |
| Green LED | 18 | 10 |
| Red LED | 19 | 11 |
| Buzzer transistor control | 23 | 12 |
| I²C SDA | 21 | 8 |
| I²C SCL | 22 | 9 |

Buttons connect between their GPIO and GND using the internal pull-ups. LED
outputs are active high and require series resistors. The buzzer output controls
the proposed transistor stage with a base resistor; the default assumes an active
buzzer. A passive buzzer needs a tone/PWM adapter. Share grounds.

The S3 proposal changed scanner RX to GPIO18. This integration deliberately keeps
the existing configurable RX16/TX17 connection on both boards. These are GPIO
numbers, not physical header positions; confirm available pins for the actual
board/flash/PSRAM variant before assembly. Pin collisions are rejected at compile
time. The earlier Proteus project inspection did not establish a verified netlist.

The shared I²C bus is fixed at **100 kHz**. The DS1307 specifies a 4.5–5.5 V VCC
supply and standard-mode I²C up to 100 kHz; its input-high minimum is 2.2 V.
Check the breakout's pull-ups: the ESP32 side must use 3.3 V logic, with pull-ups
to 3.3 V or suitable level translation if the module pulls the bus to 5 V.
Use the chosen OLED module's rated supply. Source:
[Analog Devices DS1307 datasheet, operating conditions and bus timing](https://www.analog.com/media/en/technical-documentation/data-sheets/DS1307.pdf).

Override individual pins/settings in the ignored `local_config.h`, alongside
the existing scanner settings. Optional examples:

```cpp
#define TERMINAL_OLED_ENABLED 0  // USB prompts while the display is undecided
// #define TERMINAL_OLED_SH1106 1 // SH1106 128x64; or select esp32-sh1106
// #define TERMINAL_OLED_ADDRESS 0x3D
// #define TERMINAL_BUZZER_ACTIVE_HIGH 0
// #define TERMINAL_ENABLED 0   // Original serial diagnostic only
```

## Start and record attendance

Build `esp32-sh1106` for the user's working SH1106 adapter; it is selected by
default by PlatformIO and `src/upload_script.ps1`. `esp32` retains the SSD1306 adapter.
Both compile `src/main.cpp` and enable the full physical attendance interface.
`esp32-deferred`, accuracy builds and OLED-only tests serve different workflows;
they do not run this local attendance interface.

On **ATTENDANCE** (Home), lift the finger and then present an enrolled finger.
The firmware matches it, checks the DS1307 timestamp, reads the template identity
and verifies the appended `/attendance.csv` record before displaying
**ATTENDANCE SAVED**. A repeated template on the same local calendar date shows
**ALREADY CHECKED IN**. These local records still require authorized identity and
class/session handling before becoming departmental website attendance.

Home explains missing prerequisites: **ENROLL A FINGER**, **SET CLOCK TO RECORD**,
**CHECK LOG STORAGE** or a scanner status message. **READY FOR ATTENDANCE** means
the current sensor, clock and log checks have passed. Log readback is still
required for every save. Do not format a nonempty filesystem to clear a message.

The serial `m` command is a diagnostic match test; it does not save attendance.
Diagnostic/backup commands pause automatic attendance and show
**ATTENDANCE PAUSED**. Send `a` (or use the button aliases) to return to Home.
Use MENU → Set clock → ENROLL to set the actual local date/time, and MENU →
Export log → ENROLL to print saved CSV over USB.

## OLED noise and controller choice

The display transport now explicitly selects each page and column, clears all
display RAM while the panel is off, and then writes bounded data chunks. It no
longer depends on SSD1306 horizontal-window commands, which do not provide the
same addressing behavior on an SH1106. The SH1106 profile uses its two-column
visible offset and controller-specific power setup; the I²C address alone cannot
identify the controller. No new display library is required.

The user confirmed that the full `esp32-sh1106` build works best. It is now the
default, so the normal upload command selects it without an extra option:

```powershell
& .\src\upload_script.ps1 -Port COM12
```

Both variants retain attendance and the existing GPIO21/22, 100 kHz bus. The
user's report confirms the display driver choice; attendance recording on the
complete assembly still needs its own test. Driver reference:
[Adafruit SH110x page writes](https://github.com/adafruit/Adafruit_SH110x/blob/master/Adafruit_SH110X.cpp).

## Preserved button behavior

| Context | ENROLL | DELETE | MENU |
| --- | --- | --- | --- |
| Home | Enroll with three presentations | Scan a registered finger to select it for deletion | Next page |
| Statistics | Enroll | Select finger for deletion | Next page |
| Export log | Print local CSV over USB | Select finger for deletion | Next page |
| Set clock page | Open clock editor | Select finger for deletion | Next page |
| System | Enroll | Select finger for deletion | Next page |
| Erase fingerprints page | Enroll | Hold continuously for three seconds to erase the scanner library | Home / cancel hold |
| Enrollment / lift prompt | No additional action | No additional action | Cancel |
| Delete confirmation | No additional action | A **new press**, after finger removal, confirms deletion | Cancel |
| Clock editor | Increase field; hold to repeat | Decrease field; hold to repeat | Advance year → month → day → hour → minute → save |

Menu pages return home after 20 seconds of inactivity. Finger/lift prompts time out
after 20 seconds; delete confirmation after eight seconds. The clock editor times
out after 60 seconds without a change; serial `x` also cancels it. ENROLL/DELETE
repeat only in the clock editor, starting after 500 ms, at 120 ms intervals.
Holding a key across an action boundary cannot trigger the next action. MENU wins
if pressed with another key. An early DELETE release cancels erase immediately.
OLED contrast dims after 60 seconds without user/finger activity.

Three-scan enrollment keeps the proposal's intent: extract scan 1 into buffer 1
and reject an already registered finger; require removal; extract scan 2 into
buffer 2 and merge; require removal; extract scan 3 into buffer 2 and match it
against the merged model in buffer 1. Only then store buffer 1 in a rechecked free
slot. Up to five unreadable captures can be retried, with removal between attempts.
The serial `e` command retains the existing two-scan diagnostic enrollment.

Deletion requires a successful full-library match, actual finger removal and a
fresh DELETE confirmation. The scanner's count and the target occupancy bit are
checked after a persistent change. Uncertain saves/deletes are reported as
unconfirmed; check `l` / `r` before retrying. No automatic destructive retry runs.

## Corrections to the proposal

- One scanner driver handles all commands with existing length, address, packet
  type, checksum and bounded timeout checks. The reported capacity is used rather
  than a guessed R307 maximum. Slot zero can be used if it is the last free slot.
- Image error `0x03` is distinct from no-finger `0x02`. A failed lift prompt stops
  enrollment/deletion progression. Automatic scanning requires removal before
  another presentation and runs only on Home.
- Debounced button edges replace competing IRQ/poll latches. Input sampling
  continues during UART waits, OLED chunks and log parsing. Feedback timers do
  not block the UI; no scanner commands execute from the input hook.
- A missing sensor does not trap the user outside the menu. Runtime reconnection
  checks the last working baud (57600 if none) every five seconds while idle.
  `b` retains the full baud probe; the initial boot probe is also retained.
- A stopped, malformed or absent RTC does not silently become a made-up date.
  Set-clock success requires write and readback; dates include month/leap-year
  validation, BCD checks and DS1307 12/24-hour decoding.
- A log append is flushed, closed and read back before “saved” feedback. Failed,
  full or damaged storage is reported explicitly. Existing partial/invalid CSV
  records block new appends rather than being silently ignored.
- **Deleting a finger or erasing the scanner library keeps check-in history.**
  The proposal also truncated its log on erase; that would destroy useful audit
  evidence and is unnecessary for resetting fingerprint storage. Erase therefore
  clears the fingerprint library only. Formatting local storage is a separate,
  explicitly confirmed serial operation.

## Local records and identity

The prototype writes `/attendance.csv` in ESP32 LittleFS with columns:

```text
event_uuid,device_uuid,local_datetime,slot,template_sha256,raw_score
```

`device_uuid` is generated once and saved in NVS; it is an identifier, not a device
authentication credential. Each saved event has a new event UUID. Local time is
entered manually (use the installation's local time, currently Africa/Lagos).
There is no network clock synchronization or timezone conversion.

The daily duplicate key is **template SHA-256 + local calendar date**. A scanner
slot is only its current location. Reusing a slot for different template bytes
does not inherit its former occupant's check-in; restoring identical bytes under
another slot preserves that template key. The hash can be joined to the existing
desktop backup's `template_sha256`; the portable JSON retains its own template
UUID and optional student UUID. Raw template bytes are temporarily read to compute
the hash, then the temporary application buffer is cleared. Templates remain in
scanner flash and in any explicitly saved desktop backup, not in the CSV.

A hash identifies this opaque template representation, **not a person**. Enrolling
the same finger anew may produce different bytes and a different key. It cannot
prevent one person checking in through multiple separately enrolled templates.
Student binding still needs an authorized registry. Scores remain raw unitless
values, with no invented percentage or probability. Hashes and event logs remain
linkable biometric-related records; protect exported logs as private project data.

These are **local check-ins**, not submitted departmental attendance. The existing
server attendance workflow requires an authorized course/session/student context;
the device identity API is still proposed. This change adds no HTTP request,
database write, server matcher or authorization bypass. See
[identity/API notes](../../docs/api-esp32-cheat-sheet.md) and
[template storage notes](../../docs/fingerprint-template-storage.md).

The log is capped at 256 KiB and is parsed as a stream. It is not automatically
overwritten when full. Export it before an intentional reset. Readback verifies
the current saved bytes; power-loss recovery, clock drift and flash endurance
still need bench validation.

## Upload and test

From PowerShell, close any other program using COM12, then:

```powershell
cd C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic
$pio = 'C:\Users\Ot\.platformio\penv\Scripts\platformio.exe'
& $pio run -e esp32-sh1106 -t upload --upload-port COM12
& $pio device monitor -p COM12 -b 115200
```

This uploads firmware; it does not run `Empty`, delete scanner templates or format
local storage. Normal firmware uploads preserve NVS/LittleFS with the same partition
layout. Do not use an erase-flash or upload-filesystem target to update the program.

New USB controls work even before the buttons/display are connected:

| Serial input | Action |
| --- | --- |
| `1` | ENROLL key (three scans in the UI) |
| `2` | DELETE key / fresh deletion confirmation / decrement clock field |
| `3` | MENU key / cancel active scan / advance clock field |
| `a` | Resume physical UI and automatic Home scanning |
| `p` | Pause UI and automatic scanning |
| `x` | Cancel UI action; also retained in diagnostic finger waits |
| `f`, then `FORMAT` + Enter | Format **all LittleFS files**, including existing check-in logs; scanner templates are unaffected |

Serial `2` cannot simulate a sustained physical erase hold. The existing serial
`d`, then `ERASE` + Enter, remains available for an intentional full-library erase.
Existing `r/b/c/m/e/d/l/t/u/v/h` commands retain their behavior and **pause the UI**.
The Python backup tool's `h` handshake does this automatically. The pause persists
between commands and after the tool exits; send `a` when ready to use the physical
terminal again. Button aliases `1/2/3` also resume the UI. During a maintenance pause,
physical buttons cannot interfere with backup/restore. The exact `FPBEGIN`/`FPDATA`/
`FPEND`, list and restore receipt formats are unchanged.

For a newly initialized ESP32, LittleFS may not yet be formatted. Check/export any
existing local files first; only use `f` / `FORMAT` when erasing them is intended.
The firmware never formats automatically after a mount failure.

Suggested assembly test sequence:

1. With the display/RTC absent, confirm `r`, `l` and the existing backup menu still
   work. `1` exercises three-scan enrollment with USB place/lift prompts. Confirm
   `m` and `v <ID>` against the enrolled finger, and verify backup/restore as before.
2. Power down, assemble the confirmed pin map and check I²C pull-up voltages. An
   OLED absent during boot is skipped until restart; DS1307 reads retry normally.
3. Use MENU → Set clock → ENROLL, then ENROLL/DELETE to edit and MENU to advance.
   Verify the date/time after restart and after removal of main power with the
   RTC backup battery fitted.
4. Initialize log storage only if appropriate, send `a`, remove then present a
   registered finger. Expect `MATCH` followed by `ATTENDANCE SAVED`. Repeat to check
   the daily duplicate message. Export-log must contain the saved CSV record.
5. Exercise MENU cancellation, invalid/mismatched scans, deletion timeout, an
   early erase-hold release, and fresh DELETE confirmation. Test a full erase
   only with a verified backup; confirm history is retained and restoration
   preserves the template hash.

## Validation status

For the 20 October OLED transport and attendance screen changes, see
[ATTENDANCE-DISPLAY-VALIDATION.md](ATTENDANCE-DISPLAY-VALIDATION.md). Both controller
builds and focused host regressions passed. The display choice is user-confirmed;
assembled attendance recording still needs its own validation.

Host simulation covers these controls using synthetic sensor replies and files.
Both ESP32 targets are built separately. The DS1307, OLED, physical buttons,
buzzer/LED stage, real flash logging and three-scan model validation **have not
been tested on the assembled hardware**. This integration has not been flashed
by the assistant. Previously verified physical export/erase/restore evidence
remains in the [hardware test log](../../docs/fingerprint-hardware-test-log.md).
