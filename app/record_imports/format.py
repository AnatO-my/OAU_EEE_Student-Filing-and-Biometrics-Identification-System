"""Bounded, literal CSV parsing. Identifiers are never parsed as numbers."""
import csv
import io
import re
from decimal import Decimal

from django.core.exceptions import ValidationError

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
ROSTER_COLUMNS = ["identifier_type", "identifier_value", "full_name", "surname", "phone_number", "admission_year", "mode_of_admission", "current_level"]
RESULT_COLUMNS = ["identifier_type", "identifier_value", "course_code", "academic_session", "semester", "attempt_number", "score"]


def parse_csv(kind, text):
    if kind not in ("roster", "results"):
        raise ValidationError("Choose roster or results import.")
    if not isinstance(text, str):
        raise ValidationError("csv_text must contain UTF-8 CSV text.")
    try:
        data = text.encode("utf-8", "strict")
    except UnicodeError:
        raise ValidationError("The CSV is not valid UTF-8 text.") from None
    if not data or len(data) > MAX_BYTES or "\x00" in text:
        raise ValidationError("The CSV must contain text and be at most 2 MiB, without NUL characters.")
    reader = csv.reader(io.StringIO(text.removeprefix("\ufeff"), newline=""), strict=True)
    columns = ROSTER_COLUMNS if kind == "roster" else RESULT_COLUMNS
    try:
        header = next(reader, None)
        if header != columns and not (kind == "results" and header == columns + ["full_name"]):
            if kind == "results" and header and {"matric_number", "current_courses"}.issubset(header):
                raise ValidationError("This is the converter's nested student export. Use Prepare source to convert it into result rows before previewing.")
            expected = ", ".join(columns)
            found = ", ".join("".join(char for char in cell if char.isprintable())[:50] for cell in (header or [])[:20])
            raise ValidationError(f"CSV headers must match the published template exactly. Expected: {expected}. Found: {found or '(none)' }.")
        rows = []
        for values in reader:
            line = reader.line_num
            if len(rows) >= MAX_ROWS:
                raise ValidationError("Split this CSV into imports of at most 1000 rows.")
            if len(values) != len(header):
                raise ValidationError(f"CSV row {line} has a different number of columns from its header.")
            row = {key: value.strip() for key, value in zip(header, values)}
            if any(len(value) > 1000 or any(ord(char) < 32 for char in value) for value in row.values()):
                raise ValidationError(f"CSV row {line} contains an oversized field or control character.")
            row["row_number"] = line
            rows.append(row)
    except csv.Error:
        raise ValidationError("The CSV has invalid quoting or an oversized field.") from None
    if not rows:
        raise ValidationError("The CSV contains no data rows.")
    return data, rows


def validate_identity(row):
    if row["identifier_type"] not in ("matriculation", "utme"):
        return "invalid_identifier", "Identifier type must be matriculation or utme."
    if not row["identifier_value"] or len(row["identifier_value"]) > 100:
        return "invalid_identifier", "A student identifier of at most 100 characters is required."
    return None


def roster_values(row):
    values = {key: row[key] for key in ROSTER_COLUMNS}
    if not values["full_name"] or len(values["full_name"]) > 200 or len(values["surname"]) > 100 or len(values["phone_number"]) > 30:
        raise ValidationError("A full name and valid field lengths are required.")
    for field in ("admission_year", "current_level"):
        if not re.fullmatch(r"[0-9]{1,5}", values[field]) or not 1 <= int(values[field]) <= 32767:
            raise ValidationError("Admission year and current level must be positive whole numbers.")
        values[field] = int(values[field])
    if values["mode_of_admission"] not in ("utme", "direct_entry", "transfer"):
        raise ValidationError("Admission mode must be utme, direct_entry or transfer.")
    return values


def result_values(row):
    session = row["academic_session"]
    if not re.fullmatch(r"[0-9]{4}/[0-9]{4}", session) or int(session[5:]) != int(session[:4]) + 1:
        raise ValidationError("Academic session must be consecutive YYYY/YYYY.")
    if row["semester"] not in ("harmattan", "rain"):
        raise ValidationError("Semester must be harmattan or rain.")
    if not row["course_code"] or len(row["course_code"]) > 30:
        raise ValidationError("A recorded course code is required.")
    if not re.fullmatch(r"[0-9]{1,5}", row["attempt_number"]) or not 1 <= int(row["attempt_number"]) <= 32767:
        raise ValidationError("Attempt number must be a positive integer at most 32767.")
    if not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,2})?", row["score"]):
        raise ValidationError("A literal score from 0 to 100 with at most two decimal places is required; blanks are not zero.")
    score = Decimal(row["score"])
    if not 0 <= score <= 100:
        raise ValidationError("Score must be from 0 to 100.")
    return int(row["attempt_number"]), score
