# Extract student fields from a master marks sheet

The converter can combine PDF tables, save text outside detected tables, and export
one student record per matric number, academic session, and semester. It supports
the two-row master marks sheet header used in `sample.pdf`.

## Use the converter in the portal

In **Upload results**, select the PDF. The same
converter/parser prepares supported PDFs and its `*_students.csv` or
`*_tables.csv` exports for the result review. A student export contains nested
course lists; it is recognized and expanded rather than mistaken for a
seven-column result CSV.

Supply the reviewed attempt number for converted sources. A raw `*_tables.csv`
has no session heading, so also supply its academic session and semester from
the original document. A nested student CSV already includes that context;
PDF context comes from its page headings. Unsupported/scanned layouts need a
separate conversion or OCR and return an explanatory error.

Conversion and database matching are combined in one preview action. Review
extraction issues, source locations and matched result rows before saving scores.
Literal zero marks require explicit source confirmation; undecided `NG`
marks remain unresolved. Download the CSV and conversion reports for your private
source reconciliation. Preparation does not save a database batch or change
students/results. The later saved batch contains the normalized CSV and its hash;
the original PDF, extraction trace and conversion options are not archived in it.

The command-line commands below remain available and use the same parsing and
adaptation code. Student registration stays in the Students workspace. Unknown
matric numbers hold the result batch until students are registered separately;
refresh the saved preview afterward. Conversion never creates student profiles.

## Run from the PDF

```powershell
.\.venv\Scripts\python.exe converter.py sample.pdf output --students
```

The existing table CSV and extra text file are retained. Two student files are added:

- `sample_students.csv`: one row per student; course lists and notices are JSON
  arrays inside CSV cells.
- `sample_students.json`: the same records with structured arrays for Python or
  application code.

Without `--students`, the converter retains its general table extraction behavior.

To parse files already exported, without reading the PDF again:

```powershell
.\.venv\Scripts\python.exe student_results.py output\sample_tables.csv output\sample_extra.txt
```

## Field mapping

The raw CSV begins with `source_page` and `source_table`; indices below include them.

| Student field | Source |
| --- | --- |
| Matric number | REG NO., index 3; checked against the repeated value at index 17 |
| Semester remark | SEM RMK, index 5 |
| Current courses, units, scores, grades | CURRENT SEMESTER, index 4 |
| Outstanding courses and status | OUTSTANDING COURSES, index 6 |
| Current GPA | PRESENT / GPA, index 9 |
| Previous GPA | PREVIOUS / GPA, index 12 |
| CGPA | CUMULATIVE / GPA, index 15 |
| Cumulative remark | CUM RMK, index 16 |
| Session and semester | The extra text heading for the student's source page |

Previous GPA is the value reported in the PREVIOUS group. The parser does not
reinterpret it as an immediately preceding semester GPA or recalculate GPAs.
For this document the heading is `2024/2025 HARMATTAN SEMESTER EXAMINATION RESULTS`.

Course groups align codes, units, and results by position. For example,
`SED001 SEH001 SEM001`, `(2) (2) (2)`, and `0NG 0F 85A` become three courses.
Decimal marks such as `77.5A` retain their fractional score.
`Used Semester Ratio` and special elective units outstanding are stored separately.

`F` means Failed. `NG` remains Undecided. Every recorded zero score, including
`0F` and `0NG`, retains the value zero and receives a confirmation notice. No score
is corrected or inferred. Outstanding status `R` means Resit. Other grade/status
codes are preserved without assigning an unconfirmed meaning.

Both header rows are excluded from student exports. Conflicting matric numbers,
duplicate students in the same session/semester, unsupported column orders,
misaligned course groups, and ambiguous session headings cause an error rather
than a partial student export. Raw table and text exports remain available for
inspection. Scanned PDFs require OCR before conversion.

## Read a student's record

```python
import json
from pathlib import Path

students = json.loads(Path("output/sample_students.json").read_text(encoding="utf-8"))
student = next(item for item in students if item["matric_number"] == "GLY/2016/035")
print(student["current_gpa"], student["previous_gpa"], student["cgpa"])
print(student["current_courses"])
print(student["outstanding_courses"])
print(student["notices"])
```

Run parser checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest test_student_results -v
```

## Prepare the reviewed portal import

The nested `*_students.csv` output above is an extraction report, not the portal's
result-import CSV. Reuse the structured JSON with the adapter:

```powershell
.\.venv\Scripts\python.exe tools\export_mark_sheet_csv.py output\sample_students.json private-data\mark-sheet-review --attempt-number 1
```

Choose the attempt number from the reviewed source context. It distinguishes
attempts within one course offering; do not increment it to bypass duplicates.
The adapter does not read a database or register students. It produces new files
only and refuses to overwrite an existing extraction:

- `results.csv`: the exact seven-column CSV accepted by the portal.
- `issues.csv`: missing, undecided, conflicting, over-precision and duplicate marks
  requiring review. `NG` marks are never converted into numeric zero results.
- `trace.csv`: accepted rows linked to source record/page/table, raw mark, units
  and grade. The backend still uses its configured credit units and grading scale.
- `extraction-report.json`: source/CSV hashes, reviewed attempt context and
  accepted/unresolved counts. An accepted subset is not a complete academic history.

Literal zero marks are initially held for review. After checking all such marks
against the original sheet, add `--include-reviewed-zero-scores` and choose a new
destination. Undecided `NG` marks remain unresolved even with this flag.

Upload `results.csv` in the portal's **Upload results** workspace.
Review unknown matric numbers, existing-student matches and score conflicts before
committing. Register missing students from approved biodata, then refresh the
same preview. A master mark sheet alone does not supply missing personal details.
See [student/result imports](student-result-imports.md).

Other PDF layouts, OCR and arbitrary XLSX layouts still require a reviewed
conversion to the CSV contract. The portal only accepts the supported master-sheet
PDF layout directly; a PDF file extension does not establish layout support.
