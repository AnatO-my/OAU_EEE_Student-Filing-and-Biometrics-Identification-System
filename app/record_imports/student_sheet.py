"""Parse student records from the two-row master marks sheet layout."""

import argparse
import csv
import json
import re
from pathlib import Path


MAIN_HEADER = [
    "S/N", "REG NO.", "CURRENT SEMESTER", "SEM RMK", "OUTSTANDING COURSES",
    "PRESENT", "", "", "PREVIOUS", "", "", "CUMULATIVE", "", "",
    "CUM RMK", "REG NO.",
]
SUBHEADER = [
    "", "", "", "", "", "TNU", "TCP", "GPA", "TNU", "TCP", "GPA",
    "TNU", "TCP", "GPA", "", "",
]
COURSE_CODE = re.compile(r"[A-Z]{3}\d{3}")
MATRIC_NUMBER = re.compile(r"[A-Z]+/\d{4}/\d+")
SESSION_HEADING = re.compile(
    r"(\d{4}\s*/\s*\d{4})\s+([A-Z][A-Z -]*?)\s+SEMESTER\b", re.IGNORECASE
)
CSV_FIELDS = [
    "matric_number", "semester_remark", "outstanding_courses", "current_courses",
    "previous_gpa", "current_gpa", "current_session", "current_semester", "cgpa",
    "special_elective_units_outstanding", "used_semester_ratio", "cumulative_remark",
    "notices", "source_page", "source_table",
]


def normalized_header(row):
    return tuple(" ".join(cell.split()).upper() for cell in row)


def heading_values(text):
    return {
        (re.sub(r"\s+", "", session), " ".join(semester.split()).title())
        for session, semester in SESSION_HEADING.findall(text)
    }


def parse_context(extra_text):
    """Use page headings; allow a document-wide fallback only when unambiguous."""
    all_headings = heading_values(extra_text)
    if not all_headings:
        raise ValueError("No academic session/semester heading found in the extra text.")
    default = next(iter(all_headings)) if len(all_headings) == 1 else None
    parts = re.split(r"(?m)^--- Page (\d+) ---[ \t]*$", extra_text)
    by_page = {}
    for index in range(1, len(parts), 2):
        page = int(parts[index])
        if page in by_page:
            raise ValueError(f"Repeated context section for page {page}.")
        headings = heading_values(parts[index + 1])
        if len(headings) > 1:
            raise ValueError(f"Multiple academic session/semester headings on page {page}.")
        by_page[page] = next(iter(headings)) if headings else default
    return by_page, default


def parse_current_courses(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    course_lines = []
    ratio = None
    for line in lines:
        match = re.fullmatch(r"Used Semester Ratio:\s*(\d+)\s*/\s*(\d+)", line, re.I)
        if match:
            if ratio is not None:
                raise ValueError("Multiple Used Semester Ratio entries.")
            ratio = f"{match[1]}/{match[2]}"
        else:
            course_lines.append(line)

    if not course_lines or len(course_lines) % 3:
        raise ValueError("Current courses must contain code/units/result groups of three lines.")

    courses = []
    for index in range(0, len(course_lines), 3):
        codes = course_lines[index].upper().split()
        units = course_lines[index + 1].split()
        results = course_lines[index + 2].upper().split()
        if not (len(codes) == len(units) == len(results)):
            raise ValueError("Course codes, units, and results do not align.")
        for code, unit, result in zip(codes, units, results):
            unit_match = re.fullmatch(r"\((\d+)\)", unit)
            result_match = re.fullmatch(r"(\d{1,3}(?:\.\d+)?)([A-Z]+)", result)
            if not COURSE_CODE.fullmatch(code) or not unit_match or not result_match:
                raise ValueError(f"Invalid course entry: {code} {unit} {result}.")
            score_text = result_match[1]
            score = float(score_text) if "." in score_text else int(score_text)
            if not 0 <= score <= 100:
                raise ValueError(f"Score outside 0-100 for {code}: {score}.")
            grade = result_match[2]
            courses.append({
                "course_code": code,
                "units": int(unit_match[1]),
                "score": score,
                "grade": grade,
                "grade_meaning": {"F": "Failed", "NG": "Undecided"}.get(grade),
                "raw_result": result,
                "score_requires_confirmation": score == 0,
            })
    return courses, ratio


def parse_outstanding_courses(text):
    lines = []
    elective_units = None
    for line in (line.strip() for line in text.splitlines() if line.strip()):
        match = re.fullmatch(r"(\d+) SPECIAL ELECTIVES Units Outstanding", line, re.I)
        if match:
            if elective_units is not None:
                raise ValueError("Multiple special elective unit totals.")
            elective_units = int(match[1])
        else:
            lines.append(line)
    if len(lines) % 2:
        raise ValueError("Outstanding courses must contain code/status pairs of lines.")

    courses = []
    for index in range(0, len(lines), 2):
        codes = lines[index].upper().split()
        statuses = lines[index + 1].upper().split()
        if len(codes) != len(statuses):
            raise ValueError("Outstanding course codes and statuses do not align.")
        for code, status in zip(codes, statuses):
            if not COURSE_CODE.fullmatch(code) or not re.fullmatch(r"[A-Z]+", status):
                raise ValueError(f"Invalid outstanding course entry: {code} {status}.")
            courses.append({
                "course_code": code,
                "status": status,
                "status_meaning": "Resit" if status == "R" else None,
            })
    return courses, elective_units


def reported_gpa(value):
    value = value.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError(f"Invalid reported GPA: {value!r}.")
    return float(value)


def parse_student_rows(header, rows, extra_text):
    expected = ["source_page", "source_table"] + MAIN_HEADER
    if normalized_header(header) != normalized_header(expected):
        raise ValueError("Unsupported table header; expected the master marks sheet column order.")
    by_page, default_context = parse_context(extra_text)
    students = []
    seen = set()

    for row_number, row in enumerate(rows, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(expected):
            raise ValueError(f"CSV row {row_number}: expected {len(expected)} columns.")
        body_header = normalized_header(row[2:])
        if body_header in (normalized_header(MAIN_HEADER), normalized_header(SUBHEADER)):
            continue
        try:
            page, table = int(row[0]), int(row[1])
            if page < 1 or table < 1:
                raise ValueError("Source page and table must be positive integers.")
            matric = row[3].strip().upper()
            if not MATRIC_NUMBER.fullmatch(matric):
                raise ValueError(f"Invalid matric number: {row[3]!r}.")
            if matric != row[17].strip().upper():
                raise ValueError("The two matric number columns disagree.")
            context = by_page.get(page, default_context)
            if context is None:
                raise ValueError("No unambiguous academic session/semester for this page.")
            session, semester = context
            key = (matric, session, semester)
            if key in seen:
                raise ValueError("Repeated student in the same academic session and semester.")
            current_courses, ratio = parse_current_courses(row[4])
            outstanding, elective_units = parse_outstanding_courses(row[6])
            notices = [
                {
                    "type": "zero_score_confirmation",
                    "course_code": course["course_code"],
                    "raw_result": course["raw_result"],
                    "message": "Recorded score is 0; check and confirm against the source result.",
                }
                for course in current_courses if course["score_requires_confirmation"]
            ]
            students.append({
                "matric_number": matric,
                "semester_remark": row[5].strip(),
                "outstanding_courses": outstanding,
                "current_courses": current_courses,
                "previous_gpa": reported_gpa(row[12]),
                "current_gpa": reported_gpa(row[9]),
                "current_session": session,
                "current_semester": semester,
                "cgpa": reported_gpa(row[15]),
                "special_elective_units_outstanding": elective_units,
                "used_semester_ratio": ratio,
                "cumulative_remark": row[16].strip(),
                "notices": notices,
                "source_page": page,
                "source_table": table,
            })
            seen.add(key)
        except ValueError as error:
            raise ValueError(f"CSV row {row_number}, student {row[3]!r}: {error}") from error

    if not students:
        raise ValueError("No student records found in the master marks sheet.")
    return students


def export_student_results(tables_csv, extra_text_file, output_folder=None):
    tables_path = Path(tables_csv)
    with tables_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        if header is None:
            raise ValueError("The table CSV is empty.")
        students = parse_student_rows(
            header, reader, Path(extra_text_file).read_text(encoding="utf-8")
        )

    destination = Path(output_folder) if output_folder else tables_path.parent
    destination.mkdir(parents=True, exist_ok=True)
    stem = tables_path.stem.removesuffix("_tables")
    json_path = destination / f"{stem}_students.json"
    csv_path = destination / f"{stem}_students.csv"
    json_path.write_text(json.dumps(students, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for student in students:
            flat = dict(student)
            for field in ("current_courses", "outstanding_courses", "notices"):
                flat[field] = json.dumps(student[field], ensure_ascii=False)
            for field in ("current_gpa", "previous_gpa", "cgpa"):
                flat[field] = f"{student[field]:.2f}"
            writer.writerow(flat)

    notice_count = sum(len(student["notices"]) for student in students)
    print(f"Saved {len(students)} students: {csv_path}")
    print(f"Saved structured course details: {json_path}")
    print(f"Recorded zero scores requiring confirmation: {notice_count}")
    return students


