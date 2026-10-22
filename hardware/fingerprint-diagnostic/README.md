# ESP32 fingerprint scanner diagnostic

**21 October update:** the normal `esp32-sh1106` build now includes both attendance
methods with runtime selection, confirmation, start/stop and SH1106 feedback.
See [UNIFIED-ATTENDANCE.md](UNIFIED-ATTENDANCE.md) before following older profile
instructions below. Mode changes do not require reflashing or erasing templates.

Use the [laptop downloader walkthrough](LAPTOP-DOWNLOADER.md) for USB files and
website upload handling. The same normal build also includes optional outgoing
[Wi-Fi transfer](WIFI-TRANSFER.md) for pending batches, check-in CSV and selected
enrollment backups. Wi-Fi stays off until privately configured and explicitly
requested; its receipt confirms a laptop copy, not a website/database import.

For the complete **local attendance terminal**, upload the default `esp32-sh1106`
(the user-confirmed working display adapter). `esp32` retains the alternative
SSD1306 adapter. Both compile `src/main.cpp` and start stopped. Select and confirm
Immediate to record local matched check-ins, or Deferred to save pending probes.
Send `a` to resume attendance after a diagnostic command. See
[TERMINAL.md](TERMINAL.md#start-and-record-attendance) for operation and OLED noise
troubleshooting. Display-only, accuracy and the legacy capture-only profile do not run
this physical attendance interface.

For a short standalone display check using the original OLED wiring, see
[OLED_TEST.md](OLED_TEST.md) and build the `esp32-oled-test` environment.

For statistics instead of raw matching scores, see [ACCURACY.md](ACCURACY.md).
Two separate builds evaluate whole-library identification and one claimed ID,
with TP/FP/FN/TN counts, automatic two-second scan cooldowns, optional three-key
manual tallying and private CSV recording. They leave the normal firmware and
scanner templates intact.

The supplied physical-terminal proposal is now integrated into this C++ project:
three-scan button enrollment, scan/confirm deletion, menus, optional SH1106/SSD1306 OLED,
DS1307 and checked local check-in logging. See [TERMINAL.md](TERMINAL.md) for
button mappings, pins, USB controls, corrections and the assembly test checklist.
No additional library is required. Existing diagnostic/backup commands pause the
UI until `a`; the original `e` command keeps its two-scan enrollment behavior.

A standalone C++/Arduino PlatformIO project for an **AS608**, plus unknown
scanners that implement the same **EF01 UART packet protocol**. It authenticates,
reads system parameters, and reads the number of stored templates. Optional
commands test image capture and matching against enrolled templates. `e` enrolls
a new finger in a free slot, and `d` clears all templates after explicit console
confirmation. Captures and extracted features use the scanner's volatile
buffers; successful enrollment saves the merged template in the scanner.
Persistent scanner settings are preserved. `t <ID>` exports an enrolled template;
the companion Python tool creates a portable UUID-linked JSON record and can
restore it to a free scanner slot with exact readback verification. Image export
and a server matcher remain outside this diagnostic.

For selecting a template or exporting all with file-save feedback, use the
[guided export instructions](EXPORTING.md). Start `portable_template.py menu`
after uploading the updated firmware and closing Serial Monitor.

## Connections

The supplied `revised biometric schematic.pdsprj` identifies an
**ESP32-S3-DevKitC-1**. This project includes that board and a conventional
ESP32-WROOM development-board profile. The photograph helps identify the layout,
but use the physical board and sensor connector labels to confirm the wiring.
Project-file inspection covered the archive and embedded component strings;
the project was not loaded in Proteus and no verified netlist was extracted.
GPIO16/17 below are configurable defaults based on the photograph.

The project's block labelled `FINGERPRINT MODULE` / `UART FINGERPRINT MODULE`
is a **Proteus Virtual Terminal** (`VTERM.DLL`). Its placed instance has
`BAUDRATE=115200`; the library definition's default is 9600.
It is a UART terminal placeholder, not a simulated AS608 that exposes sensor
parameters. This diagnostic is intended for a **physical scanner connected to
the ESP32**. The terminal's baud setting does not establish the physical
AS608's baud rate; the firmware probes that independently.

| Scanner signal | ESP32 connection used by this test |
| --- | --- |
| TXD (scanner output) | GPIO16 (ESP32 RX) |
| RXD (scanner input) | GPIO17 (ESP32 TX) |
| GND | ESP32 GND; share ground with any external supply |
| VCC | 3V3 for a 3.3 V AS608; confirm the rating of your particular module |
| Extra touch/wake/USB pins, if present | Not used by this diagnostic |

Use the **signal labels**, not assumed wire colours or connector order. An
unknown scanner's supply voltage must come from its own documentation. ESP32
UART signals use 3.3 V logic; a scanner with 5 V TX signalling needs a level
shifter before the ESP32 RX input. Ensure the supply can provide the module's
rated current. The LCD/OLED, RTC, buttons and buzzer are not needed for this test.

GPIO16/17 are configurable in [include/config.h](include/config.h). They are
GPIO numbers, not header positions. On ESP32 boards where they are reserved for
PSRAM or other functions, select available pins instead.

## Run with PlatformIO

1. Open **this folder** (`hardware/fingerprint-diagnostic`) in VS Code with the
   PlatformIO extension, or use it as the working directory for the commands.
2. Select the environment matching the physical board:
   - `esp32-s3`: ESP32-S3-DevKitC-1 **N8**, 8 MB flash without PSRAM; an alternative.
   - `esp32-sh1106`: conventional ESP32-WROOM board (`esp32dev`) with the SH1106
     display adapter; the default for the user's confirmed working setup.
   - `esp32`: the same board with the alternative SSD1306 display adapter.
   Adjust the board profile for a different flash/PSRAM variant.
3. Connect the ESP32 to the computer. For the S3 profile, use the development
   board's **USB-to-UART** port for uploading and the console. A board with only
   native USB needs the corresponding USB CDC configuration instead.
4. Build, upload and open the console:

```powershell
pio run -e esp32-sh1106
pio run -e esp32-sh1106 -t upload
pio device monitor -b 115200
```

Use `esp32-s3` instead for an ESP32-S3 board. If there are multiple
serial ports, run `pio device list` and specify `--upload-port COM7` and
`pio device monitor -p COM7 -b 115200`, replacing COM7 with your port. If the
PlatformIO CLI is not on PATH, use the PlatformIO terminal or its Build, Upload
and Monitor buttons in VS Code. Close other programs using the port. Press
RESET after opening the monitor if the initial report has already scrolled past.

The console runs at **115200 baud**, independently of the scanner's baud rate.
The scanner probe begins at **57600**, then tries the other standard multiples
of 9600 through 115200 and the extensions 230400/460800. A full unsuccessful
probe takes about 24 seconds. It changes only the ESP32 UART rate.

Send these characters in the console:

| Character | Action |
| --- | --- |
| `r` | Read parameters and template count again |
| `b` | Repeat authentication and baud-rate detection |
| `c` | Wait for a finger and test image capture |
| `m` | Capture, extract features, and search existing enrolled templates |
| `e` | Enroll your finger using two captures in a verified free slot |
| `d` | Clear every stored template after typing `ERASE` and Enter |
| `t <ID>` then Enter | Export an occupied slot's template; use the Python tool to save it privately |
| `l` | List actual occupied template slots |
| `t ALL` then Enter | Stream all occupied templates; use the Python menu to save verified files |
| `u` | Template import protocol; use the Python restore command |
| `v <ID>` then Enter | Capture a finger and search only the specified occupied slot |
| `x` | Cancel a finger wait or erase confirmation |
| `h` or `?` | Display help |

## Test image capture and matching

After uploading the latest firmware, open the 115200-baud console and press
RESET. Wait for authentication and the parameter report, then:

1. Send `c` and place a finger flat on the sensor when prompted. A successful
   acquisition prints `Image capture: PASS.` Lift your finger afterward.
2. Send `m` and place a finger that was previously enrolled. Success prints
   `Image capture: PASS.`, `Feature extraction: PASS.`, and a result such as
   `MATCH: template ID=7; confidence score=200 (raw sensor value).`
3. Lift the finger, send `m` again, and try a finger that was not enrolled.
   The expected result is `NO MATCH`. A poor capture of an enrolled finger can
   also produce no match, so retry with a clean sensor and stable placement.

The ID and score above are synthetic examples. The returned ID is a scanner
storage slot; it requires an external mapping to identify a person. The score
is the scanner's raw matching value, rather than a percentage probability.
Use the [score/evaluation reference](../../docs/fingerprint-score-and-evaluation-reference.md)
when preparing comparisons and the report.

The finger wait expires after 20 seconds; send `x` to cancel sooner. Sensor
operations have a separate two-second response timeout. Errors distinguish
UART/packet failures, unsuccessful acquisition and unusable fingerprint
features. `m` rereads capacity/count and searches every reported slot, including
sparse IDs. If the library is empty, `c` remains available for acquisition tests.

No Adafruit library is required. To upload from this computer's PowerShell,
close the current Serial Monitor with Ctrl+C, then run:

```powershell
cd C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic
$pio = 'C:\Users\Ot\.platformio\penv\Scripts\platformio.exe'
& $pio run -e esp32-sh1106 -t upload --upload-port COM12
& $pio device monitor -p COM12 -b 115200
```

COM12 was the user's detected CP2102 bridge; recheck `pio device list` if the
port changes after reconnecting the board.

## Clear old registrations and enroll your own finger

Uploading firmware changes the ESP32 program. The scanner keeps its fingerprint
library separately, so use its `d` command to remove the old registrations.
**This permanently deletes every stored fingerprint template.**

1. Upload the updated firmware, open the 115200-baud console, press RESET and
   wait for authentication.
2. Send `d`. At the erase prompt, type uppercase `ERASE` and press Enter within
   15 seconds. Expect `ERASED: stored templates=0.` An incorrect confirmation,
   timeout or `x` cancels the operation.
3. Send `e`. After a fresh clear, enrollment selects slot **1** on this scanner.
   Place your finger when prompted for scan 1, lift it completely when prompted,
   and place the **same finger** again for scan 2. Each finger/removal wait lasts
   up to 20 seconds and can be cancelled with `x`.
4. Expect `ENROLLED: template ID=1.` and a report showing one stored template.
5. Lift your finger, send `m`, and place that registered finger again. Expect
   `MATCH: template ID=1; confidence score=...`.
6. Send `m` with a different, unenrolled finger to check for `NO MATCH`.

Enrollment only saves after both feature extractions and model merging succeed.
Different fingers in the two scans produce an enrollment-mismatch error and
stop before saving. A save error or timeout requires a count check with `r`
before retrying, because the scanner may have saved despite a lost reply.

You can also send `e` while keeping the existing library. It reads the occupancy
table, selects a free slot and checks that slot again before saving. A count of
zero establishes a fresh library directly. If an unknown module cannot provide
the occupancy table, enrollment into its nonempty library stops rather than
guessing an ID. Every `e` command creates a new enrollment; lift the finger and
use `m` for subsequent matching tests.

## Portable template backup and restore

Recommended terminal workflow (after uploading the latest firmware and closing
Serial Monitor):

```powershell
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
& $fpPython tools/portable_template.py menu --port COM12
```

Choose a listed ID, comma-separated IDs, or `ALL`. The menu creates private
per-template JSON files and a manifest, confirms every transfer/save check, and
prints the absolute paths. No student UUID is required for an unassigned backup.
Use [EXPORTING.md](EXPORTING.md) for the complete workflow and error feedback.

The [storage and identity design](../../docs/fingerprint-template-storage.md)
explains template UUIDs, student UUIDs, scanner/gallery IDs, database bindings,
and the first physical transfer experiment. Keep UUIDs with the portable record;
scanner slot IDs can change on restore. Template hashes check byte integrity,
not finger identity. The exported representation is opaque and needs a compatible
module/matcher; a matching EF01 UART protocol alone does not establish compatibility.

Close the Serial Monitor, then run the tool from this directory. Substitute your
enrolled slot and UUIDs below; `STUDENT_UUID` etc. are placeholders. Keep real
exports in the repository's ignored `private-data/` directory.

```powershell
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
& $fpPython tools/portable_template.py --help
& $fpPython tools/portable_template.py export --port COM12 --slot 1 --student-id STUDENT_UUID --finger right_index --scanner-id SCANNER_UUID --gallery-id GALLERY_UUID --compatibility-group as608-unit-1 --out ../../private-data/fingerprint-templates/enrollment.fpt.json
& $fpPython tools/portable_template.py restore --port COM12 --record ../../private-data/fingerprint-templates/enrollment.fpt.json --target-scanner-id SCANNER_UUID --target-gallery-id GALLERY_UUID --compatibility-group as608-unit-1 --receipt ../../private-data/fingerprint-templates/restore.receipt.json
```

Generate commissioning UUIDs with `& $fpPython -c 'import uuid; print(uuid.uuid4())'`
and retain them. Use the existing database student UUID when binding a real
enrollment, or a synthetic UUID for a hardware experiment. Supply `--template-id`
on repeated exports of the same enrollment to retain its original template UUID.

Restore creates an additional copy in a free slot and never intentionally
overwrites an occupied slot. It downloads to a volatile buffer, compares readback,
checks the slot again, stores, and verifies a second readback from flash.
A pending receipt records an interrupted/uncertain attempt; inspect it before
retrying because the scanner may already have stored the bytes. `m` can return
either slot when both copies exist. Run an independent recognition experiment
after transfer using `v <restored slot ID>` to restrict the search to the copy.
It reports `SLOTMATCH <ID> <score>` or `SLOTNOMATCH <ID>`; the score is raw and unitless.
Firmware builds and synthetic tests do not confirm physical
AS608 export/restore or compatibility with a server matcher.

The firmware holds transferred bytes temporarily in RAM. It does not persist
them on ESP32 flash or send them to a database. The Python tool needs `pyserial`,
already installed in PlatformIO's Python environment; no Adafruit library is
needed. Files are JSON/Base64 with SHA-256 and CRC checks, without encryption.

## What the test can report

- Working UART rate and module-reported UART rate.
- Status register and system ID.
- Template storage capacity, stored count and remaining slots.
- Security level, device address and configured data-packet size.
- Image acquisition, feature extraction, match/no-match and raw match ID/score.
- Exported template byte count and a verified restore to a free slot.
- Timeouts, invalid packet lengths, wrong packet types, checksum failures and
  scanner error codes, including incorrect passwords.

These are values **read from the connected module**, rather than hardcoded AS608
specifications. The system ID is a protocol identifier, not a unique serial
number or reliable commercial model identifier. Packet size is the UART transfer
chunk size, not the size of an entire fingerprint template.

This test cannot establish supply voltage/current, optical DPI, image dimensions,
firmware version, or statistical recognition performance. Those need
the exact module's documentation or separate model-specific commands/tests.
Successful EF01 communication does not prove that an unknown scanner is an AS608.
Scanners using different UART protocols need a different driver.
The initial parameter report does not expose full template size. Template export
measures it from the complete received data stream.

An illustrative report might include:

```text
Detected communication rate: 57600 baud
Template capacity: 162
Security level: 3
Device address: 0xFFFFFFFF
Data packet size: 128 bytes (code 2)
Reported UART rate: 57600 baud (multiplier 6)
Stored templates: 0
Free template slots: 162
```

These numbers are examples, not measurements or guaranteed AS608 specifications.

## Changed password, address or pins

Factory settings used by this test are password `0x00000000` and address
`0xFFFFFFFF`. If your scanner was reconfigured, create the ignored file
`local_config.h` beside `platformio.ini`:

```cpp
#define FINGERPRINT_RX_PIN 16
#define FINGERPRINT_TX_PIN 17
#define FINGERPRINT_PASSWORD 0x00000000UL // Replace with the known password.
#define FINGERPRINT_ADDRESS 0xFFFFFFFFUL // Replace with the known address.
```

The password is used only for authentication and is not printed. The program
does not recover unknown passwords or discover arbitrary custom addresses.
On a valid error ACK, probing stops and reports the code so a password failure
is not mistaken for a disconnected scanner.

If every attempt times out, check the supply, common ground, crossed TX/RX,
correct GPIO numbers, known password/address and protocol. A scanner's light
turning off does not by itself establish that UART communication failed.

## Validation and implementation

The firmware uses ESP32 `HardwareSerial` and a small packet codec without a
third-party sensor dependency. It issues `VfyPwd` (`0x13`), `ReadSysPara`
(`0x0F`), `TemplateNum` (`0x1D`), `GenImg` (`0x01`), `Img2Tz` (`0x02`) and
`Search` (`0x04`), `ReadIndexTable` (`0x1F`), `RegModel` (`0x05`), `Store` (`0x06`)
and explicitly confirmed `Empty` (`0x0D`), plus `LoadChar` (`0x07`), `UpChar`
(`0x08`) and `DownChar` (`0x09`) for portable template transfer.
ACK lengths and checksums are validated before
parameters are decoded. Baud-rate arithmetic uses 32 bits so 115200 is reported
correctly. The platform is pinned to `espressif32@6.12.0` for repeatable builds.

Host protocol fixtures can be compiled with a C++ compiler:

```powershell
New-Item -ItemType Directory -Force .pio/host-tests
g++ -std=c++11 -Wall -Wextra -Werror -I include tests/protocol_test.cpp -o .pio/host-tests/protocol_test.exe
.\.pio\host-tests\protocol_test.exe
g++ -std=c++11 -Wall -Wextra -Werror -I tests/stubs -I include tests/firmware_test.cpp -o .pio/host-tests/firmware_test.exe
.\.pio\host-tests\firmware_test.exe
g++ -std=c++11 -Wall -Wextra -Werror -I tests/stubs -I include tests/enrollment_test.cpp -o .pio/host-tests/enrollment_test.exe
.\.pio\host-tests\enrollment_test.exe

g++ -std=c++11 -Wall -Wextra -Werror -I tests/stubs -I include tests/template_transfer_test.cpp -o .pio/host-tests/template_transfer_test.exe
.\.pio\host-tests\template_transfer_test.exe

python -m unittest discover -s tests -p test_portable_template.py -v
```

Build/test results are recorded in [VALIDATION.md](VALIDATION.md). Passing builds
and synthetic fixtures do not replace a run on the physical ESP32 and scanner.

## Arduino IDE alternative

PlatformIO is suitable for this test. If you prefer Arduino IDE, create a sketch,
copy the content of `src/main.cpp` into its `.ino` file and place `config.h` and
`fingerprint_protocol.h`, `portable_template.h` and `template_transfer.h` beside it.
Remove the optional `local_config.h` include
block from `config.h`, or put your overrides directly in that header. Install
Espressif's ESP32 board package, choose the matching board, and use a 115200-baud
Serial Monitor. No fingerprint library is required.

## Protocol and board references

- [Adafruit's fingerprint protocol implementation](https://github.com/adafruit/Adafruit-Fingerprint-Sensor-Library/blob/master/Adafruit_Fingerprint.cpp)
  and [command/parameter definitions](https://github.com/adafruit/Adafruit-Fingerprint-Sensor-Library/blob/master/Adafruit_Fingerprint.h).
- [Adafruit's occupancy-table and enrollment implementation](https://github.com/adafruit/Adafruit_CircuitPython_Fingerprint/blob/main/adafruit_fingerprint.py).
- [Espressif HardwareSerial documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/serial.html).
- [ESP32-S3 electrical specifications](https://documentation.espressif.com/esp32-s3_datasheet_en.pdf).
- [PlatformIO ESP32-S3-DevKitC-1 profile](https://docs.platformio.org/en/stable/boards/espressif32/esp32-s3-devkitc-1.html)
  and [regular ESP32 profile](https://docs.platformio.org/en/stable/boards/espressif32/esp32dev.html).


## Saved single-capture experiment

See [PROBE-EXPERIMENT.md](PROBE-EXPERIMENT.md) for q (fresh feature export) and
j (reload saved bytes and search one enrolled reference). The companion
`tools/probe_experiment.py` saves private probe/result files. These commands use
volatile buffers and do not enroll, overwrite or erase scanner slots. They pause
the terminal until explicit resume. The matching engine is the connected AS608;
this is a diagnostic prerequisite for deferred attendance, not an attendance
importer. Physical execution awaits verified board and COM-port details.


## Offline unidentified capture prototype

See [DEFERRED-CAPTURE.md](DEFERRED-CAPTURE.md) for the isolated esp32-deferred
profile, persistent capture files, guarded empty-partition initialization, USB
download and pending identity/clock reconciliation. This mode does not mark
student attendance or replace the legacy diagnostic terminal profile.
