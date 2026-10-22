import csv
import json
import tempfile
import unittest
from pathlib import Path

from student_results import (
    MAIN_HEADER, SUBHEADER, export_student_results, parse_current_courses,
    parse_outstanding_courses, parse_student_rows,
)


HEADING = "--- Page 1 ---\n2024/2025 HARMATTAN SEMESTER EXAMINATION RESULTS"
HEADER = ["source_page", "source_table"] + MAIN_HEADER
CURRENT = (
    "SED001 SEH001 SEM001\n(2) (2) (2)\n0NG 0F 85A\n"
    "SOC203 SOC301 SOC309\n(3) (3) (3)\n55C 0NG 24F\n"
    "SOC315 SOC411\n(3) (3)\n28F 18F\nUsed Semester Ratio: 15/18"
)
OUTSTANDING = (
    "SOC403 SOC409 SOC411\nR R R\nDSS202 SOC204 SOC309\nR R R\n"
    "SOC315 SED001\nR R\n0 SPECIAL ELECTIVES Units Outstanding"
)


def sample_row():
    return [
        "1", "1", "2", "GLY/2016/035", CURRENT, "Repeat", OUTSTANDING,
        "15", "9", "0.60", "108", "138", "1.28", "123", "147", "1.20",
        "Passed", "GLY/2016/035",
    ]


class StudentResultsTests(unittest.TestCase):
    def test_requested_student_and_repeated_headers(self):
        rows = [["1", "1"] + SUBHEADER, sample_row(), ["2", "1"] + MAIN_HEADER]
        student, = parse_student_rows(HEADER, rows, HEADING)
        self.assertEqual(student["matric_number"], "GLY/2016/035")
        self.assertEqual(student["semester_remark"], "Repeat")
        self.assertEqual(student["cumulative_remark"], "Passed")
        self.assertEqual(student["current_session"], "2024/2025")
        self.assertEqual(student["current_semester"], "Harmattan")
        self.assertEqual(student["current_gpa"], 0.60)
        self.assertEqual(student["previous_gpa"], 1.28)
        self.assertEqual(student["cgpa"], 1.20)
        self.assertEqual(student["used_semester_ratio"], "15/18")
        self.assertEqual(len(student["current_courses"]), 8)
        self.assertEqual(len(student["outstanding_courses"]), 8)
        self.assertEqual(student["current_courses"][2]["score"], 85)
        self.assertEqual(student["current_courses"][2]["course_code"], "SEM001")
        self.assertEqual(student["special_elective_units_outstanding"], 0)
        self.assertTrue(all(course["status_meaning"] == "Resit" for course in student["outstanding_courses"]))

    def test_zero_grades_stay_distinct_with_notices(self):
        student, = parse_student_rows(HEADER, [sample_row()], HEADING)
        ng, failed = student["current_courses"][:2]
        self.assertEqual((ng["score"], ng["grade"], ng["grade_meaning"]), (0, "NG", "Undecided"))
        self.assertEqual((failed["score"], failed["grade"], failed["grade_meaning"]), (0, "F", "Failed"))
        self.assertTrue(ng["score_requires_confirmation"])
        self.assertTrue(failed["score_requires_confirmation"])
        self.assertEqual([notice["course_code"] for notice in student["notices"]], ["SED001", "SEH001", "SOC301"])

    def test_misaligned_courses_fail_instead_of_truncating(self):
        with self.assertRaisesRegex(ValueError, "do not align"):
            parse_current_courses("SOC401 SOC403\n(3)\n76A 60B")
        with self.assertRaisesRegex(ValueError, "do not align"):
            parse_outstanding_courses("SOC401 SOC403\nR")

    def test_decimal_marks_are_preserved(self):
        courses, _ = parse_current_courses("SEH001 SEM001\n(2) (2)\n77.5A 0.0NG")
        self.assertEqual(courses[0]["score"], 77.5)
        self.assertEqual(courses[0]["raw_result"], "77.5A")
        self.assertFalse(courses[0]["score_requires_confirmation"])
        self.assertTrue(courses[1]["score_requires_confirmation"])

    def test_zero_special_electives_is_not_an_outstanding_course(self):
        courses, units = parse_outstanding_courses("0 SPECIAL ELECTIVES Units Outstanding")
        self.assertEqual(courses, [])
        self.assertEqual(units, 0)

    def test_conflicting_matric_numbers_and_duplicate_records_fail(self):
        row = sample_row()
        row[17] = "GLY/2016/036"
        with self.assertRaisesRegex(ValueError, "matric number columns disagree"):
            parse_student_rows(HEADER, [row], HEADING)
        with self.assertRaisesRegex(ValueError, "Repeated student"):
            parse_student_rows(HEADER, [sample_row(), sample_row()], HEADING)

    def test_unknown_schema_fails(self):
        header = HEADER.copy()
        header[10] = "NOT PREVIOUS"
        with self.assertRaisesRegex(ValueError, "Unsupported table header"):
            parse_student_rows(header, [sample_row()], HEADING)

    def test_session_is_taken_from_the_students_page(self):
        text = HEADING + "\n--- Page 2 ---\n2025/2026 RAIN SEMESTER EXAMINATION RESULTS"
        second = sample_row()
        second[0] = "2"
        records = parse_student_rows(HEADER, [sample_row(), second], text)
        self.assertEqual(records[1]["current_session"], "2025/2026")
        self.assertEqual(records[1]["current_semester"], "Rain")
        missing = sample_row()
        missing[0] = "3"
        with self.assertRaisesRegex(ValueError, "No unambiguous"):
            parse_student_rows(HEADER, [missing], text)

    def test_missing_or_ambiguous_context_fails(self):
        with self.assertRaisesRegex(ValueError, "No academic session"):
            parse_student_rows(HEADER, [sample_row()], "No heading")
        ambiguous = HEADING + "\n2025/2026 RAIN SEMESTER EXAMINATION RESULTS"
        with self.assertRaisesRegex(ValueError, "Multiple academic"):
            parse_student_rows(HEADER, [sample_row()], ambiguous)

    def test_csv_and_json_round_trip_multiline_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / "sample_tables.csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerows([HEADER, ["1", "1"] + SUBHEADER, sample_row()])
            (root / "sample_extra.txt").write_text(HEADING, encoding="utf-8")
            records = export_student_results(root / "sample_tables.csv", root / "sample_extra.txt")
            self.assertEqual(json.loads((root / "sample_students.json").read_text(encoding="utf-8")), records)
            with (root / "sample_students.csv").open(newline="", encoding="utf-8-sig") as stream:
                row, = list(csv.DictReader(stream))
            self.assertEqual(row["current_gpa"], "0.60")
            self.assertEqual(row["cgpa"], "1.20")
            self.assertEqual(json.loads(row["current_courses"]), records[0]["current_courses"])
            self.assertEqual(len(json.loads(row["notices"])), 3)


if __name__ == "__main__":
    unittest.main()
