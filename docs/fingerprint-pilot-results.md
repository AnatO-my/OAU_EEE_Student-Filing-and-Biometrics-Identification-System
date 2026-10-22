# Fingerprint recognition and RTC pilot results

Test date: 15 October 2026. These are measured results from one participant,
one enrolled finger and one designated unenrolled finger. Both methods used
the same freshly enrolled slot-1 reference. The user followed the guided
genuine/unenrolled blocks; physical finger labels are operator-supplied ground
truth, not something independently established by CSV output.

## Setup and scope

- Regular ESP32; AS608 model label supplied by the user, sensor firmware unknown.
- Scanner RX GPIO16 / TX GPIO17, 57600 baud, security level 3, capacity 150.
- Exactly one stored template, slot 1; inventory CRC32 AEBCCF9E in both runs.
- Separate automatic 1:N full-range Search and 1:1 selected-slot Search builds.
- Ten genuine and ten unenrolled-finger attempts per method; detected lift and
  a minimum two-second cooldown between results and subsequent presentations.
- DS1307 timestamps use Lagos local time, UTC+01:00, explicitly synchronized
  from the PC at the beginning of each capture.

The scanner was emptied and the reference freshly enrolled before this pilot.
A normal diagnostic matched the enrolled finger and rejected the designated
unenrolled finger before collecting these blocks. Earlier references, failed
experiments and q diagnostic captures are not pooled with these results.

## Recognition outcomes

| Measurement | 1:N identification | 1:1 verification |
| --- | --- | --- |
| Genuine attempts | 10 | 10 |
| Unenrolled attempts | 10 | 10 |
| Automatic attempts / completed decisions | 20 / 20 | 20 / 20 |
| TP / FN | 10 / 0 | 10 / 0 |
| TN / FP | 10 / 0 | 10 / 0 |
| Acquisition / communication / other sensor errors | 0 / 0 / 0 | 0 / 0 / 0 |
| Poll errors / unclassified / wrong-ID subset | 0 / 0 / 0 | 0 / 0 / 0 |
| Decision accuracy | 20/20 = 100% | 20/20 = 100% |
| Recall | 10/10 = 100% | 10/10 = 100% |
| Specificity | 10/10 = 100% | 10/10 = 100% |
| Negative false-positive rate | 0/10 = 0% | 0/10 = 0% |
| Genuine decision failure rate | 0/10 = 0% | 0/10 = 0% |
| Decision coverage | 20/20 = 100% | 20/20 = 100% |

These are percentages of observed outcomes, not the scanner's unitless matching
score. Each method has its own denominator. In 1:N the negative/genuine search
error rates correspond to the protocol's FPIR/FNIR definitions. No additional
independent physical-placement ledger was supplied; automatic counts cannot
prove the absence of completely undetected placements.

## Processing time

All times are milliseconds; each row contains ten completed searches.

| Method and case | Median total_ms | Total range | Median search_ms | Search range |
| --- | --- | --- | --- | --- |
| 1:N genuine | 897.5 | 868–1014 | 47.5 | 43–127 |
| 1:N unenrolled | 981.5 | 958–1017 | 109.5 | 73–119 |
| 1:1 genuine | 923.5 | 864–966 | 59.5 | 45–100 |
| 1:1 unenrolled | 920.5 | 789–966 | 85.5 | 46–96 |

total_ms measures image-command start through the result, excluding human
waiting, the cooldown and the subsequent RTC read. search_ms measures the
Search transaction only. These samples do not establish a statistically
significant speed difference or complete attendance/check-in throughput.

## RTC and recording integrity

| Check | 1:N | 1:1 |
| --- | --- | --- |
| Trial-linked timestamps | 20/20 | 20/20 |
| All post-sync time rows, including checks | 33 | 23 |
| Post-sync local time range | 19:40:34–19:44:27 | 19:55:38–19:58:24 |
| RTC status/date in evaluated session | All ok, 2026-10-15 | All ok, 2026-10-15 |
| Backward calendar readings | None observed | None observed |
| Median RTC minus PC receipt time, seconds | -1.547 | -0.896 |
| RTC minus PC receipt range, seconds | -1.964 to -1.038 | -1.381 to -0.423 |
| Trial event IDs | Continuous 1–20 | Continuous 1–20 |
| Recording issues log | Empty | Empty |

Trial rows, classifications and summary arithmetic were independently validated.
Each trial has exactly one linked timestamp. The 1:N capture retains an earlier
year-2000 pre-sync reading in a different session; it is excluded from post-sync
claims. Time was synchronized separately for each run, so this does not
demonstrate retention or uninterrupted timekeeping between runs.

The RTC has one-second resolution. The PC difference also includes serial and
host processing/receipt delay and depends on the PC clock. It is a functional
comparison, not calibrated absolute accuracy or long-term drift. Battery
retention, extended power interruption and long-duration drift remain untested.

## Evidence and limitations

Private capture folders under private-data/fingerprint-accuracy:

- 1:N: run-20261015-184034-UTC-6743beef, session 3A718FF9-3.
- 1:1: run-20261015-185538-UTC-056c1ba8, session 22ACA06F-3.

Each retains trial/summary CSVs, timestamps.csv, console output and issues log.
Use [the hardware log](fingerprint-hardware-test-log.md) for diagnostic history,
including earlier 1:1 failures and the corrected q diagnostic. Normal automatic
statistical scans always used one feature extraction and one Search per image.
The old q defect is not a proven explanation of every earlier failure.

This is a small, single-person, single-reference functional pilot. Repeated
finger presentations are correlated, and zero observed errors does not prove
zero underlying error probability or generalize to the student population.
With only one stored reference, the 1:N run does not test choosing among
multiple enrolled identities or performance at a larger gallery size.
Additional fingers/participants, controlled conditions, multiple-reference
identification, RTC retention and the complete attendance workflow require
separate experiments. The unperformed expanded matrix remains in the
[session plan](fingerprint-reporting-test-session.md).

## Suggested report wording

“In a single-participant pilot against a one-template gallery at security level
3, separate 1:N identification and selected-slot 1:1 verification experiments
each recorded ten genuine and ten unenrolled-finger attempts. Both produced
10 true positives and 10 true negatives, with no observed false positives,
false negatives or processing errors. Every trial had a valid post-sync RTC
timestamp. These results demonstrate operation under the tested conditions;
the small, repeated-finger sample does not establish population-wide biometric
accuracy or RTC battery retention.”
