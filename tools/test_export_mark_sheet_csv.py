import copy
import json
from pathlib import Path
import tempfile
import unittest

from export_mark_sheet_csv import export, flatten


def source():
    return [{"matric_number": "EEE/2026/0001", "current_session": "2026/2027", "current_semester": "Harmattan", "source_page": 1, "source_table": 2,
             "current_courses": [{"course_code": "EEE101", "score": 77.5, "grade": "A", "raw_result": "77.5A", "units": 3}]}]


class MarkSheetAdapterTests(unittest.TestCase):
    def test_exact_identifier_decimal_and_source_trace(self):
        rows, issues, trace, total = flatten(source(), attempt_number=1)
        self.assertEqual(rows[0]["identifier_value"], "EEE/2026/0001")
        self.assertEqual(rows[0]["score"], "77.50")
        self.assertEqual((total, len(issues), trace[0]["source_page"], trace[0]["output_row"]), (1, 0, 1, 2))
        self.assertNotIn("credit_units", rows[0])

    def test_zero_requires_review_and_undecided_never_becomes_zero(self):
        records = source()
        records[0]["current_courses"] = [
            {"course_code": "EEE101", "score": 0, "grade": "F", "raw_result": "0F"},
            {"course_code": "EEE102", "score": 0, "grade": "NG", "raw_result": "0NG"},
        ]
        rows, issues, _, total = flatten(records, attempt_number=1)
        self.assertEqual((len(rows), len(issues), total), (0, 2, 2))
        rows, issues, _, _ = flatten(records, attempt_number=1, include_reviewed_zero_scores=True)
        self.assertEqual((rows[0]["score"], len(issues), issues[0]["code"]), ("0.00", 1, "unresolved_mark"))

    def test_repeated_rows_all_reported_without_fabricating_attempt(self):
        records = source()
        records.append(copy.deepcopy(records[0]))
        rows, issues, _, total = flatten(records, attempt_number=2)
        self.assertEqual((len(rows), len(issues), total), (0, 2, 2))
        self.assertTrue(all(row["code"] == "duplicate_result" for row in issues))

    def test_context_and_precision_are_not_guessed(self):
        records = source()
        records[0]["current_semester"] = "Unknown term"
        with self.assertRaisesRegex(ValueError, "unsupported semester"):
            flatten(records, attempt_number=1)
        records = source()
        records[0]["current_courses"][0]["raw_result"] = "77.555A"
        self.assertEqual(flatten(records, attempt_number=1)[1][0]["code"], "unresolved_mark")
        records[0]["current_courses"][0]["raw_result"] = "75A"
        self.assertEqual(flatten(records, attempt_number=1)[1][0]["code"], "conflicting_score")

    def test_new_output_only_and_source_count_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            original = path / "students.json"
            original.write_text(json.dumps(source()), encoding="utf-8")
            report = export(original, path / "new", attempt_number=1)
            self.assertEqual(report["source_course_rows"], report["accepted_rows"] + report["unresolved_rows"])
            self.assertFalse(report["complete_history"])
            self.assertIn("identifier_type,identifier_value,course_code,academic_session,semester,attempt_number,score", (path / "new/results.csv").read_text())
            with self.assertRaisesRegex(ValueError, "already exists"):
                export(original, path / "new", attempt_number=1)


if __name__ == "__main__":
    unittest.main()
