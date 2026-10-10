# Teammate brief: academic result PDF to CSV

## Objective and boundary

Build a repeatable converter that extracts academic result rows from PDF into the
CSV contract below. The Django team owns database lookup, authorization, preview,
transactional import, duplicate handling, credit units, grading versions and
verification. Your converter must not write to the database or create student
accounts. This is academic results work, independent of biometric attendance.

Start with a small set of representative layouts. Text PDFs and scanned PDFs
need different extraction paths; scanned pages require OCR. Detect the page type
and report unsupported layouts. Do not assume every page in a PDF has the same
layout. Handle multi-page tables, repeated headings and split rows explicitly.

## Required CSV contract

UTF-8 encoding; comma delimiter; one header row with exactly these names/order:

```csv
identifier_type,identifier_value,course_code,academic_session,semester,attempt_number,score
matriculation,001234,EEE301,2026/2027,harmattan,1,68.00
matriculation,001234,EEE302,2026/2027,rain,1,0.00
utme,00056789,EEE101,2026/2027,harmattan,1,45.00
```

Examples are synthetic. Quote fields correctly using a CSV library; do not build
rows by joining strings manually. Standard LF or CRLF line endings are accepted.
Quoted identifiers still require spreadsheet columns to be imported as TEXT;
opening a CSV directly in Excel can strip leading zeros or change long numbers.

| Column | Meaning and rule |
|---|---|
| identifier_type | Exactly matriculation or utme, established from source/context |
| identifier_value | Existing student's identifier as text; preserve leading zeros, punctuation and case; no numeric conversion |
| course_code | Existing course code; preserve its identity; no invented codes |
| academic_session | Consecutive YYYY/YYYY, e.g. 2026/2027; never infer from today's date |
| semester | Exactly harmattan or rain; use an explicitly reviewed source-label mapping |
| attempt_number | Positive integer 1..32767 distinguishing attempts within the same offering |
| score | Academic score as a decimal string from 0.00 to 100.00, at most two decimal places |

Remove surrounding extraction whitespace. Do not impose a matric/UTME regular
expression: departmental identifier format and case-normalization policy are
still undecided. Do not convert identifiers to integers or floats.

One row represents one student's attempt at one course offering. An offering is
identified by course_code + academic_session + semester. The duplicate key is
identifier_type + identifier_value + course_code + academic_session + semester
+ attempt_number. Repeating a course in another session uses another offering;
attempt_number is not a lifetime/global count across sessions. Use 1 only where
a single attempt for that offering is established by source or reviewed context.
Never turn a repeated table row into attempt 2 just to bypass duplicate checks.

Do not export grade points, GPA, CGPA, is_verified, student UUID or credit units
as input columns. Django resolves the UUID and course offering, copies its units
and grading version, and computes the academic values. If units or grade labels
appear in the source, retain them in the extraction trace for reconciliation.

## Context, uncertainty and missing values

Academic session, semester and course may appear in headings rather than each
row. Capture that context and attach it to the appropriate rows. If absent,
require reviewer-supplied context and record that it was supplied. Proposed CLI:

```text
converter input.pdf --output-dir output --academic-session 2026/2027 --semester harmattan
```

The command is a specification for the tool you will implement, not an existing
project command. Allow explicit context to be supplied without silently treating
it as information found in the PDF. Conflicting heading/context must be flagged.

Never guess a digit, swap a student identifier, change O to 0 automatically,
infer a score from a letter grade, or replace an unreadable score with zero.
A recorded 0.00 is a valid failed result. Missing/absent/pending values belong in
the issue report until reviewed. The backend supports pending results, but this
first extraction contract keeps unresolved rows out of the accepted CSV.
OCR confidence alone cannot establish correctness. Every accepted row must have
traceable source location and a reviewable relationship to the original table.

## Deliverables per conversion

1. results.csv: rows that meet the contract; not a claim of complete history.
2. issues.csv: source file, page, source row/cell, raw value, diagnostic_code and
   explanation for every unresolved/duplicate row. Initial codes can include
   UNREADABLE_SCORE, AMBIGUOUS_IDENTIFIER, MISSING_CONTEXT, INVALID_SCORE,
   INVALID_ATTEMPT and DUPLICATE_ROW. Keep codes stable and explanations readable.
3. extraction-report.json: converter version, input filename and SHA-256 digest,
   total pages, source data-row count, accepted row count, unresolved row count,
   any excluded headings/footer counts, context/mappings applied and warnings.
4. trace.csv: output row number linked to source file/page/row, including any
   source credit-unit or grade-label values for later reconciliation.

Never silently discard a data row. Report counts must reconcile; duplicates and
unresolved rows count as issues. Re-running the same input/configuration should
produce the same results and row mapping. Keep extraction logs separate from
results.csv; do not print logging text into the CSV stream.

Rows requiring manual corrections should retain their original values and a
review record. An accepted subset must not be presented as the complete set of
student results. Graduation completeness is a separate backend requirement.

## Acceptance examples

- 001234 remains exactly 001234 after extraction and CSV parsing.
- Long UTME identifiers remain text; no scientific notation.
- Multi-page tables do not import repeated headers as results.
- Separate semesters/courses are not merged into one context.
- Score 0 is retained; a blank or OCR-ambiguous score is reported, not changed to 0.
- Scores outside 0..100 or with more than two decimals are reported for review.
- Missing/conflicting session or semester requires supplied/reviewed context.
- Duplicate keys are flagged; no fabricated attempts or silent deduplication.
- Genuine failed/repeated attempts are retained: CGPA counts both.
- Unsupported or corrupt PDFs produce a clear report, not an apparently successful empty import.
- Source row counts reconcile with accepted and unresolved rows.

Provide runnable source, dependencies, a short setup/usage README, synthetic or
redacted fixtures, automated tests for these cases and example output files.
Start by sending us output from a few representative documents before widening
layout support. Keep real student PDFs/results out of Git and public issues.

## Backend integration later

The backend will validate every row again, resolve existing students and offerings,
check the operator's current adviser scope/add-result permission, show a preview,
and commit the approved batch atomically. Imported results start unverified.
Existing student/offering/attempt matches must never be silently overwritten.
The importer will enforce safe re-import behavior and preserve source provenance.
It is not implemented yet; agree its request/response contract before wiring the
converter to a live API. The converter does not need database credentials.
