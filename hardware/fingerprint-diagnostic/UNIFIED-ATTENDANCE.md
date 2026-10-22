# Unified attendance terminal — 21 October 2026

`esp32-sh1106` now contains immediate matching and deferred capture in the same
installed program. `esp32` provides the same functions with an SSD1306 adapter.
The separate `esp32-deferred` environment is retained only for capture-controller
development; switching ordinary attendance type does not require that build.

The [laptop walkthrough](LAPTOP-DOWNLOADER.md) explains USB download and website
upload. Optional [Wi-Fi transfer](WIFI-TRANSFER.md) is included in this normal
build and is disabled until configured. On either mode's Export page, ENROLL
keeps the USB action/help and DELETE requests Wi-Fi transfer of that mode's
saved CSV or selected pending batch. The scanner's enrolled templates are not
deleted. Hold/press MENU to cancel an active wireless transfer; association and
network waits are bounded. A verified laptop receipt uses neutral export
feedback; connection, save or receipt failure uses red error feedback and leaves
all device files intact. Deliberate MENU cancellation uses neutral cancellation
feedback (both LEDs off and one short beep), with no success receipt claimed.
Enrollment backup over Wi-Fi uses the selected-slot
laptop command documented in that guide.

## Select and start a mode on the installed device

1. Upload the normal SH1106 firmware once using `src/upload_script.ps1`.
2. Press MENU until **ATTENDANCE MODE** appears.
3. ENROLL selects **IMMEDIATE**; DELETE selects **DEFERRED**.
4. Read the confirmation; a fresh ENROLL press confirms and starts the selected
   mode if its prerequisites are satisfied. MENU cancels; the prompt expires
   after 20 seconds. No selection deletes any data.
5. The **START / STOP** page controls the current mode without changing it.

Boot starts with attendance stopped in Immediate mode. Mode selection is an
operator action; deferred acquisition is never automatically armed after reset.
The most recently selected deferred batch is remembered, independently of the
running state. Menus and enrollment/deletion interrupt deferred capture; use
Start/Stop or `a` to explicitly start again. USB maintenance pauses both paths.

## Immediate matching

Lift, then present an enrolled finger. The scanner searches existing references.
A verified local CSV append produces **ATTENDANCE SAVED**. This requires a valid
DS1307 and writable LittleFS. At this checkpoint duplicates are suppressed by
template hash and local date, not by class session; the website binding and
final student/class reconciliation remain separate work.

## Deferred capture

Prepare real class-session batches using the existing laptop USB tool described
in [DEFERRED-CAPTURE.md](DEFERRED-CAPTURE.md). Provisioning a batch is not a firmware
rebuild. The **DEFERRED CLASS BATCH** menu shows the full class-session UUID;
ENROLL cycles valid saved batches. Check the class against the laptop's session
list before starting. The chosen batch is retained in NVS across power cycles.

Select Deferred and confirm to start. Captures are stored on the ESP32 with
readback/commit verification, require finger lift and do not enroll, search or
delete scanner references. **CAPTURE SAVED / PENDING MATCH** means saved evidence,
not confirmed identity or attendance. No continuously connected laptop or
internet is needed after arming. A reboot stops capture but preserves files.

The current format retains boot UUID/uptime and null calendar time. It does not
invent RTC dates. Unknown/ambiguous/out-of-roster identity and time reconciliation
remain to implement. Downloads retain device files and are not deletion receipts.
Damaged/interrupted writes and full storage stop capture rather than erase data.

## Feedback contract

The implementation is in `include/terminal_feedback.h`. The complete event table
is also included in report Appendix B (`tables/table_b_feedback.tex`).

| Event group | LEDs | Sound |
| --- | --- | --- |
| Startup | Both off | One 100 ms beep |
| Enrollment presentations accepted | Both off | None; lift/next-attempt prompt |
| Enrollment stored and checked | Green for 700 ms | One 700 ms beep |
| Immediate attendance saved | Green for 700 ms | One 100 ms beep |
| Deferred capture saved | Both off | One 100 ms beep; PENDING MATCH on screen |
| Duplicate, no-match, retry, operation/storage failure | Red for 700 ms | Two 120 ms beeps, 120 ms apart |
| Confirmed fingerprint delete/library erase | Green for 700 ms | Two 100 ms beeps, 100 ms apart |
| Start, stop, cancel, batch selection/preparation | Both off | One 100 ms beep |
| Clock saved/read back or export complete | Both off | One 100 ms beep |
| Button press | Does not interrupt outcome feedback | 20 ms click when no stronger pattern is active |
| Background readiness warning | Both off after any existing feedback expires | No repeating alarm |
| USB diagnostics/backup/restore/format | Both off; capture paused | Silent protocol operation; inspect console result |

Green never indicates startup, progress, file export, clock setting, a mode
selection or an unidentified capture. A confirmed match using a previously
enrolled/restored reference may light green even without a new enrollment during
the current boot. Sensor enrollment success is not a website database receipt.
All pulses are nonblocking; the firmware continues sampling cancellation inputs.

After USB maintenance, hold MENU for two seconds to open mode selection with
capture stopped. This is processed only after the active serial transaction has
completed. Deferred statistics show pending captures, never a count of confirmed
students; its Export page directs the operator to the laptop batch downloader.
Unassigned DELETE actions on Start/Stop and Class Batch pages are ignored.

## Scope and verification

The report explains immediate and deferred paths as distinct acquisition options
within this build. Automatic enrollment upload, backend identity reconciliation,
and real student/class attendance promotion are not implied by this integration.
Physical mode switching, LEDs/buzzer and assembled long-duration operation still
need bench validation. No sensor erase, capture deletion or backend write is part
of an ordinary mode change or this source update.
