# Attendance display correction — 20 October 2026

User follow-up: the SH1106 version works best on the physical display. PlatformIO
and `src/upload_script.ps1` now select `esp32-sh1106` by default. The explicit
`esp32` environment remains available for an SSD1306 display. This supersedes the
initial default/controller uncertainty below; no attendance-save result was
reported in that follow-up.

The normal terminal now explicitly labels Home as ATTENDANCE and reports missing
sensor, enrollment, RTC or log prerequisites. A confirmed saved record displays
ATTENDANCE SAVED; maintenance shows ATTENDANCE PAUSED with the resume instruction.
The existing match-to-local-CSV workflow remains in place; diagnostic matching
alone still creates no record, and no website attendance submission was added.

The OLED transport uses explicit page/column writes, clears every RAM page before
display-on and checks both queued byte counts and I2C acknowledgements. The new
esp32-sh1106 environment uses SH1106 power setup and a two-column visible offset;
the default esp32 environment remains SSD1306. Both enable physical attendance.

## Completed checks

- Native oled_pages, terminal and terminal_logic suites passed under C++11 with
  -Wall -Wextra -Werror. The display model starts with noisy RAM, verifies all
  eight pages, blanking, SH1106 edge columns, bounded I2C packets and failed/short
  transfers. Terminal tests cover attendance success/failure/duplicates, the
  missing-clock/storage messages, lift gating and maintenance pause/resume.
- Both esp32 and esp32-sh1106 PlatformIO builds passed: 47,008 bytes RAM and
  400,901 bytes application flash each.
- Upload-script PowerShell syntax and changed-file whitespace checks passed.

## Physical check still required

No firmware upload or new physical attendance recording was performed for this
correction. The user's photograph establishes a powered but distorted display,
not its controller identity. The panel and assembled attendance workflow still
require a physical re-upload/visual check; no claim of a resolved hardware fault
or measured final circuit is made.
