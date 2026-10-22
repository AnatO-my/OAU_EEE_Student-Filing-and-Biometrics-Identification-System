# Technical report evidence and review handoff

User instruction, 15 October 2026: retain all findings and reports for use in
the methodology, results and other sections of the final technical report.
The user will supply snippets of existing report progress for verification
and cross-checking. Review those snippets against the saved evidence rather
than relying only on conversation memory.

## Evidence to consult

- [Verified pilot results](fingerprint-pilot-results.md): final controlled 1:N
  and 1:1 outcomes, timing, RTC observations, provenance and sample limits.
- [Hardware test log](fingerprint-hardware-test-log.md): historical failures,
  erasure/restoration, enrollment, diagnostic corrections and measured results.
- [Reporting session protocol](fingerprint-reporting-test-session.md): proposed
  procedure, ground truth, denominators and the expanded tests not yet executed.
- [Score and evaluation reference](fingerprint-score-and-evaluation-reference.md):
  raw score interpretation, metric definitions and supporting sources.
- [Template storage design](fingerprint-template-storage.md): portable records,
  identity mapping, backup/restore scope and implementation limitations.
- [Accuracy implementation/procedure](../hardware/fingerprint-diagnostic/ACCURACY.md)
  and [validation record](../hardware/fingerprint-diagnostic/VALIDATION.md):
  firmware controls, synthetic regressions, build evidence and revisions.
- [Terminal design](../hardware/fingerprint-diagnostic/TERMINAL.md): buttons,
  attendance workflow and optional RTC/display/storage implementation.

Raw records remain under ignored private-data. The results document identifies
the relevant capture folders and sessions. Do not embed raw fingerprint
templates, participant identifiers or private payloads in the shared report.

## How to use the findings in report sections

| Section | Evidence and treatment |
| --- | --- |
| Methodology | Actual ESP32/scanner/DS1307 configuration, enrollment and fixed-reference procedure, separate 1:N/1:1 modes, operator ground truth, trial counts, timing definitions and RTC checks |
| Implementation | Actual C++/PlatformIO design, UART/I2C, preserved button roles, portable-template workflow and implemented attendance behavior; distinguish source implementation from hardware validation |
| Results | Verified counts and rates per method, processing-time tables, RTC timestamp completeness and recording integrity |
| Discussion | Meaning of observed errors/successes, diagnostic-order findings, historical failures, reference/gallery changes and practical implications without unsupported causal claims |
| Limitations | One participant, one reference, correlated repetitions, only ten trials per case/method, one-template gallery and untested retention/drift/population generalization |
| Conclusion | What the measured prototype demonstrates, qualified to the tested conditions |
| Future work | Multi-reference/multi-participant experiments, controlled conditions, RTC battery retention/drift and full attendance integration tests that remain unperformed |
| Appendices | Protocol, selected non-sensitive logs, calculations, build/test evidence and relevant code excerpts |

## Cross-check rules for incoming snippets

1. Compare every numerical claim, unit, percentage and denominator with the
   appropriate saved run. Keep 1:N and 1:1 results separate.
2. Distinguish proposed work, implemented behavior, synthetic tests and measured
   hardware results. Do not describe unperformed expanded tests as completed.
3. Check that methodology describes the procedure actually used, including the
   final smaller pilot scope and operator-supplied finger labels.
4. Retain historical failures and revisions where relevant. The repeated-image
   q diagnostic was unreliable; it is not a proven explanation of all earlier
   statistical 1:1 failures. Do not silently relabel or remove those failures.
5. Do not report the unitless matching score as a percentage/probability.
   Observed 100% decision accuracy is limited to each 20-attempt pilot.
6. Check the one-template-gallery limitation: this pilot did not establish
   identification among several enrolled identities or population accuracy.
7. Keep processing time separate from human waiting, cooldown and full check-in
   throughput. RTC-minus-PC receipt differences are not calibrated drift.
8. Keep UART packet size, template payload size, library capacity, occupied
   count and sensor model/firmware identity distinct. Unknown values stay unknown.
9. Check consistency across report sections and figures; flag contradictions,
   missing evidence or citation needs and suggest precise replacement wording.
10. When later measurements extend or contradict the pilot, add a separately
    identified experiment and update report claims with its provenance.
