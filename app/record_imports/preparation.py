"""Read-only preparation of existing converter outputs and native PDF tables."""
import csv
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .format import MAX_BYTES, MAX_ROWS, RESULT_COLUMNS, parse_csv
from .mark_sheet_export import COLUMNS, csv_text, flatten
from .student_sheet import CSV_FIELDS, MAIN_HEADER, heading_values, normalized_header, parse_student_rows

MAX_SOURCE_COURSES = 1000


class PreparationError(ValueError):
    pass


def validate_context(academic_session, semester, *, required=False):
    if required and (not academic_session or not semester):
        raise PreparationError("Raw master-table CSV needs a reviewed academic_session and semester; its headings are in the converter's separate extra-text file.")
    if bool(academic_session) != bool(semester):
        raise PreparationError("Supply both academic_session and semester, or leave both empty.")
    if academic_session:
        if not re.fullmatch(r"[0-9]{4}/[0-9]{4}", academic_session) or int(academic_session[5:]) != int(academic_session[:4]) + 1:
            raise PreparationError("Academic session must use consecutive YYYY/YYYY.")
        if semester not in {"harmattan", "rain"}:
            raise PreparationError("Semester must be harmattan or rain.")


def safe_filename(filename):
    filename = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stem = "".join(char for char in stem if char.isprintable())[:90].strip() or "prepared"
    return stem + "-results.csv"


def bounded_records(records):
    if not isinstance(records, list) or not records or len(records) > MAX_ROWS:
        raise PreparationError("A source must contain 1 to 1000 structured student records.")
    total = 0
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("current_courses"), list):
            raise PreparationError("The converter export must contain a JSON current_courses list for each student.")
        total += len(record["current_courses"])
        if total > MAX_SOURCE_COURSES:
            raise PreparationError("Split converter exports into at most 1000 source course rows per preparation.")


def prepared_result(records, *, source_format, data, filename, attempt_number,
                    include_reviewed_zero_scores=False, context_source="source"):
    if type(attempt_number) is not int or not 1 <= attempt_number <= 32767:
        raise PreparationError("Converted formats require an explicitly reviewed attempt_number from 1 to 32767.")
    bounded_records(records)
    try:
        rows, issues, trace, total = flatten(records, attempt_number=attempt_number,
            include_reviewed_zero_scores=include_reviewed_zero_scores)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        raise PreparationError("The converter's structured records contain invalid identities, context or course marks. Review the source export before preparing it.") from None
    normalized = csv_text(COLUMNS, rows)
    if len(rows) > MAX_ROWS or len(normalized.encode("utf-8")) > MAX_BYTES:
        raise PreparationError("The prepared CSV exceeds 1000 rows or 2 MiB. Split the source into smaller files.")
    return {"format": source_format, "csv_text": normalized, "filename": safe_filename(filename),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "summary": {"source_course_rows": total, "accepted_rows": len(rows), "unresolved_rows": len(issues)},
        "issues": issues, "trace": trace,
        "reviewed_context": {"attempt_number": attempt_number,
            "include_reviewed_zero_scores": include_reviewed_zero_scores, "context_source": context_source},
        "complete_history": False}


def read_csv_source(data):
    try:
        text = data.decode("utf-8", "strict")
    except UnicodeError:
        raise PreparationError("Choose a native PDF or a UTF-8 CSV export. Binary spreadsheet files must first be exported as CSV.") from None
    if "\x00" in text:
        raise PreparationError("The uploaded CSV contains NUL characters; export it as UTF-8 CSV.")
    try:
        reader = csv.reader(io.StringIO(text.removeprefix("\ufeff"), newline=""), strict=True)
        header = next(reader, None)
        if header is None or len(header) > 64 or any(len(cell) > 200 for cell in header):
            raise PreparationError("The CSV has no supported header row.")
        rows = []
        for row in reader:
            if len(rows) >= 1200:
                raise PreparationError("Split source tables into at most 1000 student/course rows before preparing them.")
            if len(row) != len(header):
                raise PreparationError("The CSV contains inconsistent column counts. Review its export settings.")
            rows.append(row)
    except csv.Error:
        raise PreparationError("The CSV has invalid quoting or an oversized field. Split it into smaller valid exports.") from None
    return text, header, rows


def prepare_csv(data, filename, *, attempt_number=None, academic_session="", semester="",
                include_reviewed_zero_scores=False):
    text, header, rows = read_csv_source(data)
    if header in (RESULT_COLUMNS, RESULT_COLUMNS + ["full_name"]):
        # Keep original BOM, line endings and bytes for the preview's source hash.
        try:
            _, parsed = parse_csv("results", text)
        except Exception as error:
            from django.core.exceptions import ValidationError
            if isinstance(error, ValidationError):
                raise PreparationError(" ".join(error.messages)) from None
            raise
        return {"format": "canonical_csv", "csv_text": text, "filename": safe_filename(filename),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "summary": {"source_course_rows": len(parsed), "accepted_rows": len(parsed), "unresolved_rows": 0},
            "issues": [], "trace": [], "reviewed_context": {}, "complete_history": False}
    folded = [cell.strip().casefold() for cell in header]
    if len(set(folded)) == len(folded) and set(folded) == set(CSV_FIELDS):
        records = []
        for values in rows:
            row = dict(zip(folded, values))
            try:
                courses = json.loads(row["current_courses"], parse_float=Decimal)
            except (ValueError, TypeError, RecursionError):
                raise PreparationError("The nested converter CSV contains invalid JSON in current_courses. Use its original *_students.csv export.") from None
            record = {key: row[key].strip() for key in ("matric_number", "current_session", "current_semester", "source_page", "source_table")}
            record["current_courses"] = courses
            records.append(record)
        validate_context(academic_session, semester)
        if academic_session and any(record["current_session"] != academic_session or record["current_semester"].casefold() != semester for record in records):
            raise PreparationError("The reviewed session/semester conflicts with context already recorded in the student export.")
        return prepared_result(records, source_format="student_records_csv", data=data, filename=filename,
            attempt_number=attempt_number, include_reviewed_zero_scores=include_reviewed_zero_scores)
    expected_table = ["source_page", "source_table"] + MAIN_HEADER
    if normalized_header(header) == normalized_header(expected_table):
        validate_context(academic_session, semester, required=True)
        context = f"{academic_session} {semester.upper()} SEMESTER EXAMINATION RESULTS"
        try:
            records = parse_student_rows(header, rows, context)
        except ValueError:
            raise PreparationError("The master-table CSV does not match the supported two-row marks-sheet layout. Check repeated matric columns, aligned course/units/marks and source context.") from None
        return prepared_result(records, source_format="master_tables_csv", data=data, filename=filename,
            attempt_number=attempt_number, include_reviewed_zero_scores=include_reviewed_zero_scores,
            context_source="reviewer")
    expected = ", ".join(RESULT_COLUMNS)
    found = ", ".join("".join(char for char in cell if char.isprintable())[:50] for cell in header[:20])
    raise PreparationError("Unsupported CSV headers. Expected normalized result columns (" + expected + "), the converter's *_students.csv, or *_tables.csv. Detected columns: " + found + ".")


def prepare_pdf_in_process(data, filename, *, attempt_number=None, academic_session="", semester="",
                           include_reviewed_zero_scores=False, strategy="lines"):
    """Worker entry: isolated from request lifetime and database credentials."""
    from .pdf_tables import PDFPreparationError, extract_pdf_tables
    validate_context(academic_session, semester)
    try:
        extracted = extract_pdf_tables(io.BytesIO(data), strategy, max_pages=20, max_rows=1200,
            max_chars=200000, require_text=True)
        if extracted["header"] is None:
            raise PreparationError("No supported table was detected. Try text extraction for borderless native PDFs, or export the reviewed CSV.")
        context = extracted["extra_text"]
        headings = heading_values(context)
        if academic_session:
            provided = (academic_session, semester.title())
            if headings and any(value != provided for value in headings):
                raise PreparationError("The supplied academic session/semester conflicts with a PDF heading. Review each page's context.")
            if not headings:
                context += f"\n{academic_session} {semester.upper()} SEMESTER EXAMINATION RESULTS"
        try:
            # The legacy CLI serializes page/table integers through CSV first.
            # Keep that exact parser input contract in the in-memory path too.
            table_rows = [[str(cell) for cell in row] for row in extracted["rows"]]
            records = parse_student_rows(["source_page", "source_table"] + extracted["header"], table_rows, context)
        except ValueError:
            raise PreparationError("The PDF table or session headings do not match the supported master marks-sheet layout. Provide the converter's reviewed CSV or supply missing session/semester explicitly.") from None
        return prepared_result(records, source_format="master_sheet_pdf", data=data, filename=filename,
            attempt_number=attempt_number, include_reviewed_zero_scores=include_reviewed_zero_scores,
            context_source="reviewer" if academic_session and not headings else "source")
    except PreparationError:
        raise
    except PDFPreparationError as error:
        raise PreparationError(str(error)) from None
    except Exception:
        raise PreparationError("The PDF is corrupted, encrypted or unsupported. Provide an unencrypted native PDF or a reviewed CSV export.") from None


def prepare_pdf(data, filename, **options):
    # Parsing potentially hostile compressed PDF streams occurs in a short-lived
    # process. Timeout/complexity limits cannot strand a Django request thread.
    attempt = options.get("attempt_number")
    if type(attempt) is not int or not 1 <= attempt <= 32767:
        raise PreparationError("Converted formats require an explicitly reviewed attempt_number from 1 to 32767.")
    environment = {key: value for key, value in os.environ.items() if key in {
        "PATH", "PATHEXT", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}}
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    request = json.dumps({"filename": filename, "options": options}).encode("utf-8") + b"\n" + data
    try:
        process = subprocess.Popen([sys.executable, "-m", "record_imports.prepare_worker"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment, **flags)
        try:
            output, _ = process.communicate(request, timeout=25)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            raise PreparationError("PDF preparation exceeded 25 seconds. Split it into smaller CSV/PDF files.") from None
    except OSError:
        raise PreparationError("The PDF preparation worker could not start. Check the installed PDF dependencies.") from None
    if process.returncode or len(output) > 4 * MAX_BYTES:
        raise PreparationError("PDF preparation failed within its resource bound. Use a smaller native PDF or a reviewed CSV export.")
    try:
        result = json.loads(output.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise PreparationError("PDF preparation could not produce a valid result. Use the converter's CSV export.") from None
    if "error" in result:
        raise PreparationError(result["error"])
    return result


def prepare_source(data, filename, **options):
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise PreparationError("Upload a nonempty PDF or CSV file of at most 2 MiB.")
    if data.startswith(b"%PDF-"):
        return prepare_pdf(data, filename, **options)
    options.pop("strategy", None)
    return prepare_csv(data, filename, **options)
