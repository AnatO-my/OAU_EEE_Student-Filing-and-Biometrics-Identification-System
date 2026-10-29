# Upload master mark-sheet results

The portal's **Upload results** workspace converts a master mark-sheet PDF to
result CSV, matches existing students by matriculation number and saves reviewed
scores. Student registration is handled separately under **Students → Register
student**. A mark sheet never creates an incomplete student record or login
account. Importing results sends no guardian emails.

## Department workflow

1. Open **Upload results**, select the PDF and enter the reviewed attempt number
   for its course offerings. Session, semester, course codes and marks are read
   from the supported master-sheet layout. A normal result CSV already contains
   its per-row attempts; existing converter CSVs also remain accepted.
2. Choose **Convert and preview scores**. The portal converts and matches the
   result rows in one action, without changing student records or scores. Review
   extracted marks, unresolved entries, student matches and corrections. The
   converted CSV and source reports can be downloaded; no manual re-upload is
   needed.
3. Unknown matriculation numbers wait for separate student registration. Register
   the student from approved biodata under **Students**, then return through
   **Your import history** and refresh the saved result preview. No part of a
   blocked batch is committed until its flagged rows are resolved.
4. Approve each differing score with a reason, confirm review against the original
   sheet and save. New/corrected results require separate result verification.

Only missing source context needs manual entry in the optional settings. A raw
`*_tables.csv` has no session heading, so supply its academic session and semester
from the original PDF. Context already present in a source cannot be silently
overridden. The attempt number is never guessed or incremented to bypass an
existing result.

Part-advisers need the corresponding student/result permissions and an active
assignment for the student's current level/session. HOD access covers all levels.
Historical mark sheets never change a student's current level. No identifier or
name is guessed. A name conflict, when the optional name column is supplied,
must be resolved before result import.

## CSV contracts

Files contain at most 1000 data rows and 2 MiB of UTF-8 CSV. Columns must match
the templates exactly, including order. Identifiers are text: preserve leading
zeros and punctuation, and import spreadsheet identifier columns as text before
exporting. Matching ignores outer whitespace and letter case, using the shared
student identity registry. Retained UTME aliases resolve to the same student UUID.

Separate roster API contract (retained for existing integrations; it is not part
of the **Upload results** workspace):

```csv
identifier_type,identifier_value,full_name,surname,phone_number,admission_year,mode_of_admission,current_level
matriculation,SYNTHETIC/0001,Synthetic Example Student,Example,,2026,utme,100
```

Surname and phone may be blank. Other required details must come from an
approved source; the importer does not invent them. Existing biodata is never
overwritten by a student-list upload. Matching profiles are unchanged; conflicting
name/admission/level/contact details require explicit record review.

Result header (the existing extraction contract):

```csv
identifier_type,identifier_value,course_code,academic_session,semester,attempt_number,score
matriculation,SYNTHETIC/0001,EEE101,2026/2027,harmattan,1,68.00
```

An optional `full_name` may be added as the eighth column for identity checks.
Each row identifies one student, course offering (course/session/semester) and
attempt. The course offering and published grading version must already exist.
Zero is a valid literal score; blank, undecided, nonfinite, unreadable and
over-precision marks are blocked. Repeated rows never become another attempt.

The same stored result/score is skipped. A different score requires correction
permission and a reason; the change is audited and clears verification. An
unmatched student remains staged until registration is completed. Any blocked
row prevents the entire batch from committing.

The preparation step reuses the existing PDF converter, student parser and
structured-output adapter described in [PDF extraction](pdf-student-extraction.md).
It recognizes supported headers from content rather than assuming that every
file ending in `.csv` uses the result-import schema. The nested student export
contains course lists inside cells; preparation expands these into one result
per row. Raw table exports retain the converter's two-row master-sheet layout.
Only the defined two-row master marks-sheet layout is supported; other departments
are compatible only when columns/order/course blocks match. pdfplumber reads
embedded text/tables, with no OCR. Image-only PDFs need external OCR; scanned PDFs
with an existing text layer can work if extraction/layout quality is sufficient.
Unsupported layouts and XLSX files need a separate reviewed conversion; choosing a file in the browser does not establish support.

Preparation makes no database changes. It reports unresolved marks, including
undecided `NG` entries, separately and never substitutes zero. Literal zero marks
require the explicit source-review option when converting. The accepted subset
is not a complete academic history. Keep the source and downloaded reports
private. The command-line converter and adapter remain available.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/imports/` | Paginated metadata for the caller's own batches |
| POST | `/api/imports/prepare/` | Recognize/convert a source file without saving records |
| POST | `/api/imports/previews/` | Stage an immutable source and build its preview |
| GET | `/api/imports/{id}/` | Inspect the caller's saved preview or receipt |
| POST | `/api/imports/{id}/refresh/` | Recheck matches/data/scope and create a new preview revision |
| POST | `/api/imports/{id}/commit/` | Atomically apply the reviewed batch and save a durable receipt |

History accepts an optional `kind=results` or `kind=roster` filter before
pagination. The result workspace requests `kind=results`; invalid values return
400. Omitting the filter retains the original own-batch history contract.

Preparation uses multipart form data with `file`, optional `attempt_number`,
`academic_session`, `semester`, `include_reviewed_zero_scores` and PDF extraction
`strategy` (`lines` or `text`). A converted source requires the attempt number;
raw table CSV requires both session and semester. Supplied context must agree
with any context already present in a student export or PDF heading. The normal
result CSV already supplies context and attempts per row.

The response contains `format`, normalized `csv_text`, an output `filename`,
`source_sha256`, accepted/unresolved/source counts, `issues`, `trace`,
`reviewed_context` and `complete_history: false`. Format names are `canonical_csv`,
`student_records_csv`, `master_tables_csv` and `master_sheet_pdf`. Files are at
most 2 MiB; conversion is limited to 1000 source course rows, and PDFs to 20 pages.
PDF parsing runs in a separate process with a 25-second timeout. Preparation
checks active result-import access before extraction and makes no database writes.

The portal submits normalized CSV plus the returned source_context to preview.
The context contains format, source_sha256, csv_sha256 and records with all defined
converter fields. Saved imports retain this evidence and bind it to the exact CSV
hash, student identifiers and periods. They do not archive the original PDF or
converter file; keep it private for source reconciliation. Context supplied through
HTTP is evidence submitted by an authorized reviewer, not an authenticated source
document or proof that the source itself is correct. Older batches cannot recover
reported figures already discarded by earlier preparation versions.

Preview body:

```json
{"kind":"results","request_id":"client-generated-UUID","filename":"results.csv","csv_text":"the exact UTF-8 CSV text"}
```

`kind` is `roster` or `results`. Repeating the same request UUID and source
recovers the same preview. Reusing that UUID with another source is rejected.

Responses contain `id`, `request_id`, `kind`, `filename`, `file_sha256`, `status`,
`revision`, `preview_digest`, `summary`, `rows`, `can_commit` and `receipt`.
Summary counts include total, new students, new results, unchanged, corrections
and blocked. Every row has its source row number, action, diagnostic code and
message. Existing-student IDs appear only within the caller's permitted scope.

Commit body:

```json
{"preview_digest":"the saved 64-character digest","correction_approvals":[{"row_number":2,"reason":"Compared against the approved corrected sheet."}]}
```

An empty approvals list is used when no corrections exist. Every correction
must be approved exactly once, and other rows must not be approved as corrections.
The server rechecks current authorization, records, offering/grading data and
the reviewed digest under locks. A stale preview returns 409 and changes nothing.
Refresh and review it again; the client never retries a write automatically.

The durable receipt records created student/result counts, corrected results,
unchanged entries and commit time. Repeating the same committed request returns
that receipt without another write. After an uncertain response, retrieve this
same batch's receipt before doing anything else. A new upload is not receipt
recovery.

Each import saves the uploader, immutable source CSV, file hash, parsed rows,
review snapshot and commit receipt. Changes retain source row numbers and
before/after values, including correction reasons. These data remain protected
by authentication, owner access and current scope; they must remain private in
database backups. This audit covers import changes and identifier promotion,
not every historical action elsewhere in the application.

## Database update

Two additive migrations are required: `students.0007_student_identifier_registry`
and `record_imports.0001_initial`. The identity migration preserves existing
UUIDs/display values and refuses ambiguous legacy identifiers without merging
or deleting students. Back up and stop local writers before migration. See
[student identity](student-registration.md) and [the laptop guide](local-laptop.md).

## Source-reported averages and discrepancies — 23 October 2026

Preparation now carries current/previous reported GPA, reported CGPA, remarks,
outstanding-course status, current course raw text/units/grade/score, Used Semester
Ratio, special elective units, notices and page/table references into source_context.
The parser still extracts no names, course titles, department, faculty, level or
other structured biodata. Missing reported averages remain missing. F and NG are
not interchangeable, and NG/missing marks cannot become accepted scores.

Preview accepts optional source_context for results; canonical seven-column CSVs
without it retain their existing contract and cannot invent reported figures.
The context and exact CSV hash are part of request-id identity. Changing either
requires a new request. Preview/refresh/detail/commit return source_performance,
including per-student source period, source evidence and comparison. A valid
import can commit with an unresolved GPA/CGPA discrepancy; all score/identity,
correction approval, scope and stale-review safeguards remain in force.

SourcePerformance records preserve immutable source evidence and the import-time
comparison in the same transaction/receipt as results. Committed retries create no
additional observations. review_status stays unresolved; no resolution/edit API is
introduced. A later numerical match does not resolve the saved discrepancy.

The interim comparison convention is two decimal places, ROUND_HALF_UP and zero
tolerance, exposed as two_decimal_half_up_zero_tolerance_v1. This is a documented
implementation choice pending institutional precision/tolerance decisions. Each
metric exposes reported, calculated, signed calculated-minus-rounded-reported
difference and status (matching, different, not_reported, not_comparable). The
original reported decimal remains available. Previous reported GPA is a separate
field and is not compared without a known previous-period binding.

Calculations reuse academics.calculate_weighted_average and saved units/grading
versions, including repeated/failed attempts. Preview projections are explicitly
provisional: they do not verify database results. Live website comparisons require
verified recorded results and use the corresponding period for GPA and all
attempts through that period for CGPA, excluding future periods. Missing or
unverified inputs produce not_comparable. History completeness is not established
by this source; numeric differences remain review evidence, not proof of error.

The existing scoped staff and own-student GPA/CGPA endpoints now also return
source_reports. They expose source figures, provenance, live comparison,
comparison_at_import and unresolved review state. Existing gpa/cgpa values remain
system-calculated. The portal emphasizes those values and shows discrepancy/source
details; pending source reports do not replace calculation or verification rules.
No source observation triggers guardian delivery or changes grading policy.

Migration record_imports.0002_importbatch_source_context_sourceperformance is
required before deploying this code. It has only been applied in disposable tests;
no shared/Aiven database was migrated. Follow the existing backup/update procedure.
Resolution authority/states, source correction, final tolerance/precision and
complete-history comparability remain open policy work. No automatic GPA-based
blocking or extraction-confidence threshold was added.
