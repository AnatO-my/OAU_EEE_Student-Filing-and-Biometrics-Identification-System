# Short OLED functionality test

## Top-two-row integrity test - 28 October 2026

The current terminal uses the SH1106 adapter. Its dedicated
`esp32-oled-integrity` test uses that same `oled_pages.h` transport, GPIO21/22
and 100 kHz I2C, with automatic detection at `0x3C`/`0x3D`. It sends no scanner
commands and performs no filesystem, RTC or network operations.

Run the prepared PowerShell launcher from any directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic\run_oled_test.ps1"
```

The launcher defaults to COM12; add `-Port COM7` for another board port.
It builds the test, verifies the live partition layout and uploads only the
application at 57600 baud before opening the serial monitor at 115200.
Use `-BuildOnly` to compile without accessing the board. The previous SSD1306
test remains available with `-Test Basic`.

Press EN/RESET after the serial monitor opens. Watch at least one complete
cycle (approximately one minute):

1. **Numbered text:** rows 1-8 display the same digit sample. The first two
   text rows occupy pixel y=0..15; the six lower rows occupy y=16..63.
2. **White and black:** look for missing dark lines, stuck lit pixels or noise.
3. **Horizontal and vertical stripes, then their inverses:** alternate individual
   pixel rows/columns so adjacent lines can be compared.
4. **Opposite checkerboards:** the squares should remain regular over the panel.
5. **Top-only and lower-only fills:** check that y=0..15 changes cleanly between
   white and black, with the lower region showing the opposite fill.
6. **Eight-pixel bands:** each numbered text-row region lights separately.
7. **Single-pixel-row sweep:** a full-width horizontal line moves through every
   y position from 0 to 63, pausing longer over the top 16 pixel rows.

The serial output names each step and the tested y range. Send these commands
with Enter (CR/LF is ignored):

| Command | Action |
| --- | --- |
| `p` | Pause/resume the sequence; the held pattern is still rewritten |
| `n` | Next pattern, band or pixel row; remains paused if already paused |
| `t` | Hold the numbered text grid for comparison or a photograph |
| `r` | Restart the automatic cycle |
| `h` | Print the test instructions |

Every refresh rewrites all eight display pages, including while paused.
Successful I2C writes establish communication, not physical pixel integrity.
Record which text rows or pixel y positions are affected, the pattern name,
whether the lower rows are clean, and whether noise returns while paused.
The photograph supplied on 28 October shows apparent corruption in the top
two text lines; it does not establish the cause. The user subsequently reported
issues on lines 2, 4, 6, 8, 10 and 12, and confirmed these are individual pixel
lines. They fall within the top 16-pixel band whether counted from zero or one.

Preparation validation on 28 October: Windows PowerShell syntax/help and the
launcher's build-only run passed. `esp32-oled-integrity` compiles with the pinned
ESP32 framework. Native C++11 checks pass for all 64 pixel rows, eight bands,
top/lower masks, complementary patterns and repeated text samples; the existing
SSD1306/SH1106 page-transport tests also pass. No board upload was made during
this preparation.

**The terminal now reserves y=0..15.** Its six logical text rows render at
y=16..63 through the shared `terminal_screen.h` renderer. Notices, clock editing,
maintenance, mode selection and menu footers all use this region. Home keeps
mode/run state, finger instructions, readiness and counts visible; template
totals remain on Statistics. Deferred screens retain their pending-identity
wording, and the class-session UUID remains complete across two lines.
The integrity test deliberately continues to exercise all 64 pixel lines.
Avoiding the damaged band is a layout workaround; it does not establish or
repair the underlying cause. Visual confirmation of the revised terminal is pending.

Workaround validation: the `esp32-sh1106` terminal build passes. Native C++11
checks with warnings treated as errors pass for the shared screen renderer,
OLED transport, legacy terminal actions, combined attendance modes, unified
capture and Wi-Fi transfer UI. The renderer tests check a blank top 16-pixel
band, the last character/footer position, clearing stale pixels and framebuffer
bounds. Menu tests check all nine pages and the complete two-line class UUID.

Ctrl+C closes the monitor. To restore the user's working terminal, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic\src\upload_script.ps1" -Port COM12
```

## Original SSD1306 test

This separate PlatformIO/Arduino build follows the supplied original MicroPython
code: **SSD1306, 128x64, I2C address 0x3C or 0x3D**. It needs no extra libraries.

## Alternative: Adafruit text test from oled_partial.cpp

The supplied `src/oled_partial.cpp` is also available as its own build. PlatformIO
installs Adafruit SSD1306, GFX and their dependencies for this environment only:

```powershell
pio run -e esp32-oled-partial
pio run -e esp32-oled-partial -t upload --upload-port COM12
pio device monitor -p COM12 -b 115200
```

Use the same GPIO21/22 wiring below. This test shows **OLED Ready!** and a counter
that updates every second. Type text in Serial Monitor and press Enter to replace
the message. Up to 80 characters are displayed, with smaller text for longer
messages. The display keeps showing the most recent message as the counter runs.

The test probes both `0x3C` and `0x3D`, which correspond to the module's **8-bit
write address labels `0x78` and `0x7A`**. It reports `ACK` separately from driver
initialization. If neither responds, it still attempts initialization at `0x3C`
to exercise the supplied library sketch. `Driver ready` describes software setup;
confirm the visible text and counter to establish display operation. Press RESET
after changing wiring. See the [Adafruit SSD1306 API](https://adafruit.github.io/Adafruit_SSD1306/html/class_adafruit___s_s_d1306.html).

## Connect to the regular ESP32

| OLED label | ESP32 |
| --- | --- |
| SDA | GPIO21 |
| SCL | GPIO22 |
| GND | GND |
| VCC | 3V3, if your OLED module supports a 3.3 V supply |

Follow the module's printed pin labels; connector order varies. No buttons,
fingerprint sensor or clock are required. Use 3.3 V I2C signal levels.

## Run

From `hardware/fingerprint-diagnostic`:

```powershell
pio run -e esp32-oled-test
pio run -e esp32-oled-test -t upload
pio device monitor -b 115200
```

If `pio` is not on PATH, use the PlatformIO terminal or select **esp32-oled-test**
in VS Code's PlatformIO project tasks. Close other serial monitors before upload.
Press RESET after opening the monitor to see the initial I2C scan.

The test environment uses a slower **115200 baud upload** for reliability.
If upload reports `Failed to communicate with the flash chip` or
`Packet content transfer stopped`, the test has not started yet. Unplug USB,
disconnect all external wiring, reconnect USB and retry the upload on the bare
ESP32. If it succeeds, unplug USB before reconnecting the OLED to **GPIO21/22**.
The **GPIO8/9** mapping in the original MicroPython code is for an ESP32-S3;
GPIO6-11 are used by flash on this regular ESP32. If the bare board still fails,
try another USB data cable and a direct USB port. See
[Espressif's upload troubleshooting](https://docs.espressif.com/projects/esptool/en/latest/esp32/troubleshooting.html).

The screen repeats **white -> black -> checkerboard A -> checkerboard B**, holding
each for two seconds. Both checkerboards cover the whole screen with opposite
8x8 squares. Confirm the patterns visually, including the edges; a successful I2C
response alone cannot establish that the panel lights correctly.

- No device at `0x3C`/`0x3D`: check power, common GND and the SDA/SCL connections.
- `0x68` alone is a clock response; the OLED has not been detected.
- A detected address with a blank or distorted screen: confirm the module really
  uses an SSD1306 controller with 128x64 resolution. An SH1106 needs another driver.
- After changing wiring, press RESET to rerun the scan.

Uploading selects this temporary test as the ESP32 program. To restore the main
application, upload the user's working SH1106 environment again:
`pio run -e esp32-sh1106 -t upload`.
This test sends no fingerprint commands and writes no attendance files.

Validation: `esp32-oled-test` compiled successfully on 15 October 2026 with the
pinned ESP32 framework. The user's subsequent boot log confirms it ran on the
ESP32, but its scan found no responding I2C device. Visible OLED operation has
not been confirmed. The separate `esp32-oled-partial` Adafruit build also compiles;
its physical display result remains pending.

References: [Espressif Wire/I2C API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/i2c.html)
and [Solomon Systech SSD1306 datasheet](https://gabotronics.com/download/datasheets/ssd1306.pdf).
