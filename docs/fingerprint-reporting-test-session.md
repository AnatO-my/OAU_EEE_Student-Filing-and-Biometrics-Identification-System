# Fingerprint and RTC reporting session

Prepared 15 October 2026. This is a proposed single-participant pilot protocol,
not a completed result or a population accuracy claim. Keep real finger/slot
mappings, raw console and trial logs in ignored private-data storage. Use the
[firmware controls](../hardware/fingerprint-diagnostic/ACCURACY.md) alongside
this session plan.

## 1. Readiness and diagnostic evidence

The latest inspected capture, run-20261015-181222-UTC-011daae4, shows successful
scanner authentication at 57600 baud and successful enrollment at slot 7, with
seven templates in the gallery. It also contains twelve genuine-labelled 1:1
no-match results against slot 7. Which physical finger was presented must be
confirmed by the operator before interpreting those labels as ground truth.
RTC time initially synchronized to 2026 but subsequent trial reads report year
2000. The cause of this change is not established. Preserve this capture as
diagnostic evidence; do not pool it into a controlled new experiment.

First establish a repeatable method and trustworthy absolute timestamps:

1. Pause with `p`. If necessary, `b` probes the scanner; record the reported
   baud, security, capacity and stored count. A connection failure is not an
   empty-library measurement.
2. Stop the recorder, then start it with `--new-session --sync-rtc`. Confirm
   `ACCRTC SET VERIFIED`, then `w`. Verify ten advancing readings of the actual
   current Lagos date/time, not merely status `ok`.
3. Select a positively known enrolled finger with `t <ID>` + Enter. Run `q`,
   lift, then place that exact finger once. Current q runs one method per fresh
   image: repeat q with lift/re-presentation to cycle selected Search, direct
   Match and full Search. Repeated processing of one image affected earlier
   diagnostic versions. `q` does not add statistics.
4. Press `z` immediately afterward. If RTC time changed to an incorrect date,
   stop the timing experiment and preserve both readings and the diagnostic.
5. Document any method defect before the reporting run. A method that rejects
   known genuine fingers is reportable as observed failure; do not keep
   repeating or changing implementation until only successful trials remain.
   If implementation changes, label a new revision and retain old evidence.

`ok` checks the clock's calendar/running bit; it does not establish correct
absolute time. Use the PC comparison and calendar date as well.

## 2. Fix references and label fingers

Use one participant label, P01. Choose three distinct known enrolled fingers,
G1–G3, and three distinct fingers you know have never been enrolled anywhere in
the current gallery, U1–U3. If fewer are available, reduce the declared plan
before starting and report the actual finger count. Do not invent labels for
unknown old templates or infer ground truth solely from the match outcome.

Privately record:

| Label | Participant | Finger description | Enrolled slot | Negative pairing |
| --- | --- | --- | --- | --- |
| G1 | P01 | Fill privately | Fill | U1 |
| G2 | P01 | Fill privately | Fill | U2 |
| G3 | P01 | Fill privately | Fill | U3 |
| U1 | P01 | Fill privately; never enrolled | None | G1 |
| U2 | P01 | Fill privately; never enrolled | None | G2 |
| U3 | P01 | Fill privately; never enrolled | None | G3 |

Enroll any needed genuine reference using `e` before data collection. If it
reports an existing match, establish that finger's correct mapping rather than
creating a duplicate. Do not enroll U1–U3. Existing unlabelled library entries
may remain, but record the full actual gallery size. Do not erase anything as
part of this protocol without a separate explicit decision and verified backup.

Freeze the gallery and security for both test modes. Photograph/note the
assembly version, scanner model label, firmware revision and UART/I2C pins.
Write unknown sensor firmware version as unknown. Use a dry, clean sensor and
ordinary consistent placement as the baseline. Change one condition at a time
in separately labelled experiments.

## 3. Predeclared pilot matrix

| Test mode | G1/U1 pair | G2/U2 pair | G3/U3 pair | Planned total |
| --- | --- | --- | --- | --- |
| Whole-library 1:N | 10 genuine + 10 unenrolled | 10 + 10 | 10 + 10 | 60 presentations |
| Selected-slot 1:1 | 10 genuine + 10 different finger | 10 + 10 | 10 + 10 | 60 presentations |

This is 120 physical presentations across two separately reported methods:
30 genuine and 30 impostor presentations per method. The proposed counts are
a practical exploratory pilot, not a power calculation or certification
sample. Three fingers are not three participants. These are selected
finger/reference pairs, not an exhaustive all-pairs verification study.

Keep the same references and pairings for both modes. Run 1:N first, then 1:1,
and state this fixed order as a limitation; a later controlled comparison can
counterbalance order across sessions. A future 1:1 test can add other enrolled
fingers as impostors, in a separately labelled negative category. In 1:N an
already-enrolled different finger is not an impostor.

## 4. Record one pair at a time

Use a separate capture folder per mode/pair, six folders in the full plan.
This keeps U1/U2/U3 labels unambiguous even though negative 1:N rows have no
expected slot. Keep a private notes.md beside each run with its labels,
condition, mode, planned count, slot, gallery size, revision and exceptions.

Upload the appropriate accuracy environment, then start the recorder with
`--new-session`. Use `--sync-rtc` when initially setting the clock, not repeatedly
when testing retention/drift. Check `z` at the beginning/end of each run.

For each pair:

1. Keep fingers off the scanner. Enter `t <G slot>` + Enter, then `a`, then `g`.
   Confirm the printed test, source, case, target, security and gallery count.
2. Wait for readiness, present G once, await the result, then lift. Allow the
   two-second cooldown and detected lift before another presentation. Repeat
   for exactly ten planned physical presentations of the same G finger.
3. Press `p`, then `s`. Record the number of physical placements and any
   completely undetected placements, cancellations or unusual handling.
4. Remove the finger, press `i`, confirm the case changed, then use only the
   paired U finger for ten presentations. Do not change target in the 1:1 test.
5. Press `p`, `s`, `z`, then Ctrl+C. Preserve console.log, trials.csv,
   summary-history.csv, latest-summary.csv, timestamps.csv and issues log.

Do not discard a rejection/error, press manual tally keys in auto mode, or
rescan it until it passes and call that one trial. An unsuccessful presentation
still belongs to the planned dataset. Start each new pair in a new RAM session
and new host capture folder, not by repeatedly overwriting a summary.

### Physical presentations versus automatic attempts

The automatic firmware does not count a finger that produces only no-finger
responses. Start each placement after readiness; if no result appears within
five seconds, remove the finger, pause, and record an undetected presentation
in the private operator notes with its ordinal/uptime context. Do not replace
it silently to force ten automatic rows. Resume with `r`, wait for rearming,
then continue the remaining planned presentations. A result arriving late
must be reconciled against the notes so one placement is not counted twice.

Record physical presentations P and automatic established attempts A separately.
Reconcile P to recorded outcomes plus undetected placements and documented
invalid/cancelled cases. If alignment is ambiguous, mark the affected block as
having uncertain presentation counts; do not invent end-to-end statistics.
Optional manual-mode data is a separate experiment, not an addition to the
automatic confusion matrix.

## 5. Statistics to report separately for each mode

| Statistic | Definition / required evidence |
| --- | --- |
| Sample | One participant, actual distinct fingers, physical P, automatic A, completed decisions D |
| Confusion counts | TP, FN, TN, FP, plus wrong-ID subset of FN in 1:N |
| Genuine success / recall | TP / (TP + FN) |
| Genuine decision failure | FN / (TP + FN); includes wrong identity in this 1:N implementation |
| Negative false-positive rate | FP / (FP + TN) |
| Specificity | TN / (TN + FP) |
| Decision accuracy | (TP + TN) / D, D = TP + FN + TN + FP |
| Balanced accuracy | Half of recall + specificity; both cases must have completed decisions |
| Decision coverage | D / A; also state acquisition, communication and other sensor errors separately |
| Physical end-to-end success | (TP + TN) / P, only with reconciled physical placements/labels |
| Timing | Median and range of total_ms and search_ms, separate genuine/impostor outcomes; state n |
| RTC | Valid dated trial timestamps / expected timestamps; flagged/missing/stalled/backward rows; offset from PC |

Show each rate as numerator/denominator and percentage. Zero denominator is NA.
For 1:N, call the negative search error FPIR and genuine search failure FNIR
under the stated expected-ID rule. The firmware's compact FPR/FNR field names
are retained in CSV; explain their operational definitions in the report.
See [NIST's fingerprint search metrics](https://fingerprint.nist.gov/frifte/e1n/results/dermalog%2B0003/metrics.html).

Do not pool methods, manual/auto sources, different settings, changed galleries,
or exploratory/debug trials into one headline accuracy. Report per-finger
counts before combining; a single poor reference should remain visible.
Preserve failed/changed-method versions as separate evidence.

Repeated scans from the same fingers are correlated. Avoid treating 120
presentations as 120 independent people. If presenting binomial confidence
intervals, identify the method and independence assumption; do not claim
population uncertainty from this single-person pilot. Zero observed errors
means 0/n, not a demonstrated zero true error probability. See
[NIST's binomial interval guidance](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

The existing total_ms is image-command start to result, excluding human waiting
and cooldown; search_ms is command to Search ACK. It is not total check-in
throughput. A rejected search still has a valid latency; do not omit it from
an explicitly all-completed-search latency summary. No EER/ROC or liveness
claim follows from this single-threshold decision test.

## 6. Separate RTC retention experiment

First obtain ten correct advancing `w` readings after explicit sync and
record PC differences. Capture timestamps for fingerprint trials too. If the
date reverts, retain that failure and investigate before calling event times
trustworthy.

For retention: stop capture, note RTC and PC time, turn off main power for
60 seconds measured by the operator, reconnect, and start a new capture
without --sync-rtc. Run `z` and `w`; compare elapsed RTC/PC time and calendar
continuity. Record battery/module details and whether retention passed. This
one-minute functional test is not a long-term drift measurement. Drift needs
a separate longer interval without resetting the clock and a stated reference
clock/measurement uncertainty.

## Report template

“A single-participant pilot used [F] enrolled and [U] unenrolled fingers against
a fixed gallery of [N] templates at security level [L]. Separate 1:N and 1:1
experiments contained [P] physical presentations and [A] automatic established
attempts each. [D] completed decisions yielded TP=[...], FN=[...], TN=[...],
FP=[...]. Processing errors and undetected presentations were reported
separately. Median processing time was [...] ms over [...] trials. RTC time was
checked against [...] and retention was [measured outcome / not tested]. These
results describe the tested participant, references and conditions.”

Fill only with validated results; retain the actual trial counts if an
experiment stopped early or failed.
