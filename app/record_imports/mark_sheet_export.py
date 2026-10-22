"""Adapt the existing master-sheet converter's structured JSON to reviewed CSV.

This only writes new local extraction files. Database lookup, authorization and
reviewed import remain in Django. It never guesses an identity or a missing mark.
"""

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import sys


COLUMNS = ["identifier_type", "identifier_value", "course_code", "academic_session", "semester", "attempt_number", "score"]
ISSUE_COLUMNS = ["source_record", "source_page", "source_table", "identifier_value", "course_code", "raw_result", "code", "message"]
TRACE_COLUMNS = ["output_row", "source_record", "source_page", "source_table", "raw_result", "source_units", "source_grade"]


def flatten(records, *, attempt_number, include_reviewed_zero_scores=False):
    if not isinstance(records, list) or not records or not 1 <= attempt_number <= 32767:
        raise ValueError("Supply structured student records and a reviewed attempt number from 1 to 32767.")
    candidates, issues = [], []
    total = 0
    for index, student in enumerate(records, 1):
        if not isinstance(student, dict) or not isinstance(student.get("current_courses"), list) or not student["current_courses"]:
            raise ValueError(f"Source record {index} has no structured current_courses list.")
        identifier = student.get("matric_number")
        session = student.get("current_session")
        semester = student.get("current_semester")
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier.strip()) > 100 or any(ord(char) < 32 for char in identifier):
            raise ValueError(f"Source record {index} has no valid textual matriculation number.")
        if not isinstance(session, str) or not re.fullmatch(r"[0-9]{4}/[0-9]{4}", session) or int(session[5:]) != int(session[:4]) + 1:
            raise ValueError(f"Source record {index} has no reviewed academic session.")
        if not isinstance(semester, str) or semester.casefold() not in ("harmattan", "rain"):
            raise ValueError(f"Source record {index} has an unsupported semester; supply an explicit reviewed mapping upstream.")
        for course in student["current_courses"]:
            if not isinstance(course, dict):
                raise ValueError(f"Source record {index} contains an invalid course entry.")
            total += 1
            source = {"source_record": index, "source_page": student.get("source_page", ""), "source_table": student.get("source_table", ""),
                      "identifier_value": identifier.strip(), "course_code": course.get("course_code", ""), "raw_result": course.get("raw_result", "")}
            def reject(code, message):
                issues.append({**source, "code": code, "message": message})
            code = course.get("course_code")
            if not isinstance(code, str) or not code or len(code) > 30 or any(ord(char) < 32 for char in code):
                reject("invalid_course", "A literal course code is required.")
                continue
            raw = course.get("raw_result")
            match = re.fullmatch(r"([0-9]{1,3}(?:\.[0-9]{1,2})?)([A-Z]+)", raw or "") if isinstance(raw, str) else None
            if not match or match.group(2) not in set("ABCDEF"):
                reject("unresolved_mark", "The source mark/grade is missing, undecided or unsupported; review it against the original sheet.")
                continue
            try:
                score = Decimal(match.group(1))
                reported = Decimal(str(course.get("score")))
            except InvalidOperation:
                reject("invalid_score", "The structured score is not a literal decimal.")
                continue
            if not reported.is_finite() or not 0 <= score <= 100 or reported != score or course.get("grade") != match.group(2):
                reject("conflicting_score", "The raw mark and structured score/grade disagree.")
                continue
            if score == 0 and not include_reviewed_zero_scores:
                reject("zero_requires_review", "A recorded zero requires explicit source review; it has not been converted to a missing mark.")
                continue
            row = dict(zip(COLUMNS, ["matriculation", identifier.strip(), code, session, semester.casefold(), attempt_number, format(score, ".2f")]))
            trace = {key: source[key] for key in ("source_record", "source_page", "source_table", "raw_result")}
            trace.update(source_units=course.get("units", ""), source_grade=course.get("grade", ""))
            candidates.append((row, trace, source))
    grouped = {}
    for candidate in candidates:
        row = candidate[0]
        key = (row["identifier_value"].casefold(), row["course_code"], row["academic_session"], row["semester"], row["attempt_number"])
        grouped.setdefault(key, []).append(candidate)
    accepted, trace = [], []
    for values in grouped.values():
        if len(values) > 1:
            for _, _, source in values:
                issues.append({**source, "code": "duplicate_result", "message": "Repeated student/course/session/semester/attempt requires review; no extra attempt was invented."})
            continue
        row, location, _ = values[0]
        accepted.append(row)
        trace.append({"output_row": len(accepted) + 1, **location})
    return accepted, issues, trace, total


def csv_text(columns, rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export(source, destination, *, attempt_number, include_reviewed_zero_scores=False):
    source, destination = Path(source), Path(destination)
    data = source.read_bytes()
    if len(data) > 32 * 1024 * 1024:
        raise ValueError("Split source exports larger than 32 MiB before adapting them.")
    # Decimal avoids another binary-float conversion of the upstream JSON score.
    records = json.loads(data.decode("utf-8-sig"), parse_float=Decimal)
    rows, issues, trace, total = flatten(records, attempt_number=attempt_number, include_reviewed_zero_scores=include_reviewed_zero_scores)
    results = csv_text(COLUMNS, rows)
    report = {
        "adapter_version": 1, "source_filename": source.name,
        "source_sha256": hashlib.sha256(data).hexdigest(), "source_course_rows": total,
        "accepted_rows": len(rows), "unresolved_rows": len(issues), "complete_history": False,
        "results_sha256": hashlib.sha256(results.encode("utf-8")).hexdigest(),
        "reviewed_context": {"attempt_number": attempt_number, "include_reviewed_zero_scores": include_reviewed_zero_scores},
    }
    files = {"results.csv": results, "issues.csv": csv_text(ISSUE_COLUMNS, issues), "trace.csv": csv_text(TRACE_COLUMNS, trace),
             "extraction-report.json": json.dumps(report, indent=2) + "\n"}
    if any((destination / name).exists() for name in files):
        raise ValueError("An extraction output already exists. Choose a new destination directory.")
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        with (destination / name).open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="The existing converter's *_students.json output")
    parser.add_argument("destination", type=Path, help="A new output directory")
    parser.add_argument("--attempt-number", type=int, required=True, help="Reviewed attempt within this offering; never inferred from duplicate rows")
    parser.add_argument("--include-reviewed-zero-scores", action="store_true", help="Include literal zero marks after reviewing them; undecided NG marks remain unresolved")
    options = parser.parse_args()
    try:
        report = export(options.source, options.destination, attempt_number=options.attempt_number,
                        include_reviewed_zero_scores=options.include_reviewed_zero_scores)
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Mark-sheet export failed: {error}", file=sys.stderr)
        return 1
    print(f"CSV prepared: {report['accepted_rows']} result rows; {report['unresolved_rows']} unresolved. No database changes made.")
    print("Review issues.csv and trace.csv against the source before uploading results.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
