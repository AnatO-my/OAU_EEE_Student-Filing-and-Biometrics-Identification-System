# Short OLED functionality test

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
