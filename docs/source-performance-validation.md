# Source-reported averages and Chapter 3 reconciliation — 23 October 2026

## Implemented

The existing upload/prepare/preview/review/commit workflow remains primary.
Preparation now retains the parser's source records, reported current/previous
GPA and CGPA, extraction fields and source hashes alongside normalized result CSV.
The optional source_context is validated against exact CSV bytes, student/period
bindings and literal source scores; unresolved NG cannot become a numeric result.
Canonical result CSV without reported context keeps its earlier contract.

ImportBatch retains source_context and the review digest. Atomic commit writes
SourcePerformance records for matched student-periods, retaining source values,
provenance, the import-time comparison and unresolved review status. Receipt retries
remain idempotent. Reported figures never replace calculated figures. Current GPA
and CGPA endpoints add scoped source_reports, including the live period-bound
comparison and immutable comparison_at_import. The portal emphasizes calculated
averages and provides visible discrepancy/source details before and after commit.
An import discrepancy remains visible even when a later live calculation matches.

No source resolution or editing action was added. The interim comparison is
ROUND_HALF_UP to two places, zero tolerance; this is an implementation convention,
not institutional policy. Preview projections are provisional, use the existing
calculator and do not verify saved results. Live comparisons require verified
records. CGPA uses all attempts through the source period; completeness remains
not_established. Previous reported GPA has no invented previous-period binding.

## Verification

- Full isolated PostgreSQL 18.6 run: 523 tests passed, no skips, 176.969 seconds.
  This run preceded the last two regression tests and response-provenance addition.
  Its stopped cluster/logs remain under tmp/attendance-postgres-fqmfoo8w.
- Finalized import suite on a new PostgreSQL 18.6 cluster: 49 tests passed, no
  skips, 16.022 seconds. Includes 11 source-performance cases plus existing import,
  preparation, correction, permission, receipt and real contention coverage.
  The stopped cluster/logs remain under tmp/attendance-postgres-im6icbf6.
- Final portal run: 145 tests passed; production build and ESLint passed. Vite
  retains a warning about a main bundle slightly above 500 kB.
- Focused preparation/performance SQLite run passed; migration drift/system checks
  and git diff --check passed. Only disposable databases were migrated.
- Tests use synthetic records, actual small selectable-text PDF fixtures, native
  PDF/CSV preparation, layout/image-only rejection, repeated matriculation checks,
  literal zero/NG distinctions, source persistence, non-blocking acceptance,
  blocked invalid identities/scores, correction approvals, stale review, retries,
  period-bounded all-attempt calculations and own-student access isolation.
- No new live-browser end-to-end discrepancy demonstration was performed. React
  regression tests cover calculated-value emphasis, source details and retained
  unresolved state. Prior dated browser evidence is kept distinct from these tests.

## Report reconciliation

Updated the existing private Chapter 3 and linked requirements/document tables in
 docs/report-review/report-prototype/. The broad HOD brief remains distinct from
team technical choices, with no invented interview study or measured retrieval
baseline. Guardian sharing/messages are core requirements. Supporting-document
filing accepts images independently of PDF/CSV academic result import. The single
layout and non-OCR converter limits, extracted/non-extracted fields, discrepancy
handling and remaining policy choices are explicit.

Document upload and selected connected portal journeys are described as implemented
based on current source and dated synthetic integration evidence; download/list,
complete revision history and operational task evaluation are not claimed complete.
Historical recognition experiments and biometric architecture were not altered.

The app compiler timed out. Existing MiKTeX XeLaTeX subsequently compiled the entire
report to output/chapter3-check/main.pdf (100 pages), with package installation
and shell escape disabled. First-pass bibliography/cross-reference rerun warnings
remain; this output is a syntax/build check, not a publication-ready report export.
The report-review directory remains excluded by the existing Git ignore policy;
source edits are local and no commit/push was made.

## Deployment and policy limits

Apply record_imports.0002_importbatch_source_context_sourceperformance through the
normal backed-up migration process before deploying this code. No shared/Aiven
migration, source data import, real email, or biometric-record test was performed.
Older batches cannot recover source figures discarded by older preparation code.
Submitted source hashes/metadata provide traceability, not source authentication;
the original uploaded PDF is not archived by this importer.

Final tolerance/rounding, incomplete-history interpretation, who may resolve a
review, resolution states and source-correction procedures still require decisions.
No extraction-confidence or GPA blocking threshold has been inferred.
