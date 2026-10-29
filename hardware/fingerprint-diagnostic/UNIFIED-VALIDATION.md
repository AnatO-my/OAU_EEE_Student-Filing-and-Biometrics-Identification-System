# Unified attendance and feedback validation — 21 October 2026

## Implementation

The default SH1106 build compiles the local-matching terminal and deferred
controller together. CaptureControl separates UI orchestration from the
controller; the UI exclusively schedules the active acquisition path. Mode
confirmation, start/stop and prepared-class selection require no firmware swap.
Boot leaves acquisition stopped. Deferred batch selection is retained in NVS,
while arming is always explicit after reboot. No switch erases data.

Semantic feedback uses a nonblocking pulse scheduler. Green is limited to
verified enrollment, immediate-log save and deliberate reference deletion.
Pending captures and nonbiometric acknowledgements stay neutral. Error/retry
patterns and success patterns cannot be truncated by lower-priority key clicks.

## Automated checks

The complete host script passed 17 native suite/variant executions and all 62
Python tests. Focused terminal, runtime-mode and actual unified-device fixtures
were rerun after the final menu/readiness refinements and passed with
`-std=c++11 -Wall -Wextra -Werror`.

The fixtures check:

- Exclusive immediate/deferred acquisition, explicit selection and confirmation,
  stopped boot, timeout/cancel and refusal to start without required setup.
- Actual deferred capture through the combined UI: no Store/Delete/Empty/Search,
  no immediate attendance append, one acquisition client and a pending-save result.
- Held-finger gating, selected batch retained across simulated restart, explicit
  re-arming, and fresh MENU cancellation during GenImg before a file is saved.
- Maintenance pause, two-second physical MENU handover into stopped selection,
  read-only framed exports without UI text inside the transfer, and preserved data.
- Correct mode-specific statistics/export prompts and ignored unassigned Delete
  actions on Start/Stop and Class Batch pages.
- Waveform timing, click priority, millisecond rollover and green/neutral/error
  distinctions; existing storage corruption, interrupted-write and capacity cases.

The unified SH1106 and legacy capture-only ESP32 builds compile. Final unified
size: 55,768 bytes RAM and 415,809 bytes application flash. Script syntax and
changed-file whitespace/conflict checks passed.

## Report

Report Chapter Three now compares the acquisition options and their actual
integration limits; Appendix B defines feedback, controls, recovery and future
website/reconciliation states. The report compiles, and the changed pages were
rendered and inspected for wrapping, page breaks and table alignment.

## Remaining physical/integration work

No firmware flash, scanner erase, new physical scan or database write was
performed for this change. Bench tests must confirm physical button switching,
display text, LED/buzzer timing and sustained/reboot behavior on the assembled
terminal. Automatic enrollment upload/database binding, compatible identity/time
reconciliation and student/class attendance promotion remain separate gaps.

## Connected red-LED check — 29 October 2026

COM12 responded at 115200 baud; scanner UART was 57600 baud, with capacity 150
and eight stored templates. With the finger kept off the scanner, the existing
enrollment finger-wait screen reached ACTION TIMED OUT. The user heard two short
beeps but observed no external red LED. The visual red-LED check therefore did
not pass; buzzer feedback alone does not verify the GPIO19 voltage or LED wiring.
No firmware was flashed. Read-only reports before/after both showed eight stored
templates. The terminal was left paused after the test. Next inspect wiring,
polarity/resistor/common ground and measure GPIO19 during error feedback before
attributing the failure to hardware or firmware.
