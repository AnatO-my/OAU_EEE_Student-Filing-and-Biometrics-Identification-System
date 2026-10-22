# Fingerprint scores and evaluation reference

Prepared 14 October 2026 for use after assembly and when writing the project report.
This is an evaluation plan, not a set of measured recognition results.

Related files: [terminal diagnostic](../hardware/fingerprint-diagnostic/README.md),
[validation evidence](../hardware/fingerprint-diagnostic/VALIDATION.md),
[report framework](report-framework-and-methodology.md), and
[portable template design](fingerprint-template-storage.md).

## What the confidence score means

Report the AS608 result as a **raw, unitless matching score**. Higher values
indicate stronger matching according to the sensor's algorithm. Adafruit exposes
this field as a `uint16_t` and describes larger numbers as stronger matches in its
[class reference](https://adafruit.github.io/Adafruit-Fingerprint-Sensor-Library/html/class_adafruit___fingerprint.html).

The score is not a percentage, probability of identity, physical quantity, or
linear measure of similarity. A score of 160 is not necessarily twice as strong
as 80. A 16-bit field can represent 0–65535, but that does not establish the
algorithm's practical score range. Scaling a score to 0–100 does not make it a
calibrated probability.

Suggested console/report label: `Fingerprint matching score: 124 (raw, unitless)`.
That number is illustrative, not a measurement from this terminal.

## Suitable comparisons

Compare repeated raw scores within the same scanner, firmware, security setting,
reference templates and test procedure. Preserve these conditions when comparing
placement, assembly revisions or capture conditions. A changed enrollment creates
a changed reference, so record it as a new experimental batch.

For comparisons across scanners or matchers, use measured recognition outcomes,
error rates and latency with stated gallery sizes and operating settings. Equal
score values, or equal nominal security-level labels, do not establish equal
operating points. NIST explains the threshold/error tradeoff and the distinction
between verification and identification in
[A Tale of Two Errors](https://www.nist.gov/blogs/taking-measure/tale-two-errors-measuring-biometric-algorithms).

## What the current match test observes

The diagnostic's `m` command performs **1:N identification**: it searches the
scanner's library and returns an accepted slot ID and score, or a no-match/error.
It does not perform a claimed-identity 1:1 verification experiment. The slot must
be mapped separately to the person/student it represents.

Scores are printed only for accepted matches. Record unavailable scores as `N/A`,
including no-match, capture failure and communication failure; do not invent a
score of zero. The mean of printed scores describes the accepted subset only.
It cannot establish overall recognition accuracy. Accepted-only scores also do
not support a complete ROC/DET curve or an equal-error-rate estimate: those need
a suitable experimental protocol and the necessary decision/score observations.

## Proposed measurements after assembly

Define one presentation trial before collecting data and record every outcome.
The following are project evaluation definitions; state their denominators in
the report.

| Measurement | Definition | Unit |
| --- | --- | --- |
| End-to-end correct identification | Correct returned IDs / all valid enrolled-finger presentation trials | % and count |
| False positive identification rate (FPIR) | Unenrolled-finger completed searches returning any enrolled ID / all unenrolled-finger completed searches | % and count |
| Top-1 enrolled-finger identification failure (FNIR) | Completed enrolled-finger searches returning no match or the wrong ID / all enrolled-finger completed searches | % and count |
| Acquisition failure | Trials producing no usable image/features / all valid presentation trials | % and count |
| Communication failure | Trials stopped by transport/protocol errors / all valid presentation trials | % and count |
| Search latency | Search-command transmission to receipt of the complete valid search response | ms |
| Extraction plus search latency | Successful image-capture ACK to final search response | ms |
| Matching score | Sensor-returned accepted-match score | Raw, unitless |

Count wrong-identity and no-match outcomes separately even when combining them
for FNIR. Acquisition/transport failures enter the end-to-end denominator but
are separate from completed-search error rates. Predeclare how cancellations and
invalid presentations are excluded, log them, and avoid silently dropping failed
trials. Human finger-placement waiting time is separate from algorithm latency.
Report timing counts and medians, with ranges or percentiles where supported.

## Trial log to implement/use

Record session ID, trial ID, pseudonymous finger label, enrolled/unenrolled
category, expected slot ID, returned ID or `N/A`, and outcome: correct ID, wrong
ID, no match, acquisition failure, communication failure, or cancellation.
Include the score when returned and elapsed times with their start/end events.

Also record scanner instance/model label, known firmware revision (or unknown),
terminal firmware revision, assembly revision, security level, actual gallery
size and test condition. Keep identifiable trial logs in private working storage;
aggregate results are normally sufficient for the report. Raw biometric bytes
are not needed to evaluate scores.

**Implementation status (15 October 2026):** the normal diagnostic's `m` command
still displays outcomes and accepted scores. Separate
[accuracy-test builds and a CSV recorder](../hardware/fingerprint-diagnostic/ACCURACY.md)
now implement fixed-gallery 1:N identification and selected-slot 1:1 checks,
genuine/impostor blocks, TP/FP/FN/TN, separate processing errors, processing/search
timing, automatic two-second cooldowns, optional manual tallies and count-based
rates. Expected IDs label ground truth in 1:N without restricting its search.
The 1:1 build searches only the claimed ID. Raw matching scores are not used to
compute these rates. Operator participant/condition notes and real assembled
hardware data remain necessary; implementation/synthetic checks are not measured
biometric accuracy. The firmware does not implement every proposed experimental
metadata field or statistical uncertainty calculation.

## Assembly test procedure

1. Run `r` and record the actual settings and occupied count. The user's initial
   hardware report showed regular ESP32, RX GPIO16/TX GPIO17, 57600-baud scanner
   UART, security level 3 and capacity 150. It had nine stored templates at that
   time; recheck the count after clearing/enrollment.
2. Enroll each evaluation finger once with `e` and record its returned slot.
   Use `m` for independent repeat probes rather than enrolling on every trial.
3. Freeze the gallery/settings for a batch. Keep the same references for a
   pre/post-assembly comparison. Start a new batch after enrollment or firmware
   changes that affect matching.
4. Predeclare genuine and unenrolled trials, lift the finger between captures,
   and record all outcomes. Change one condition at a time where possible.
5. Calculate outcome rates using the declared denominators. Add accepted-score
   distributions as supporting observations, with the accepted sample count.
6. State the limits of the sample. Repeated trials of one finger demonstrate
   operation; they do not establish accuracy for a student population.

Zero observed false identifications means `0/n` in this experiment, not a proven
zero underlying error rate. Report counts, sample limits and appropriate
uncertainty. NIST discusses sample-dependent biometric uncertainty in its
[confidence-interval study](https://www.nist.gov/publications/comparison-confidence-intervals-large-operational-biometric-data-parametric-and-non).

## Report wording to fill in after testing

Methodology: “Identification was evaluated using independent enrolled and
unenrolled finger presentations against a fixed gallery of [N] templates at
security level [L]. Expected identities, returned identities, failures and
defined processing times were recorded. The sensor's unitless matching score
was retained as supplementary evidence for accepted matches.”

Results: “Of [G] valid enrolled-finger presentation trials, [C] returned the
correct identity. Among [I] completed unenrolled-finger searches, [F] returned an
enrolled identity. Acquisition and communication failures were [A] and [E].
Median search latency was [T] ms over [K] completed searches. Accepted-match
scores had [summary] under the stated configuration.”

Replace every placeholder with measured evidence. Use past tense only after
performing the procedure; do not report a score as ‘[score]% confidence’.
