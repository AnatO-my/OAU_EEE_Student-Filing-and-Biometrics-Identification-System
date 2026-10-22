"""Synthetic regression coverage for the real converter-to-import bridge."""
import csv
from decimal import Decimal
import hashlib
import io
import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .format import RESULT_COLUMNS
from .models import ImportBatch, ImportChange
from .preparation import PreparationError, prepare_source
from .student_sheet import CSV_FIELDS, MAIN_HEADER, SUBHEADER
from .test_imports import ImportFixture, csv_text


def source_record(courses=None):
    return {"matric_number": "SYNTHETIC/2026/001", "semester_remark": "Passed",
        "outstanding_courses": [], "current_courses": courses or [{"course_code": "EEE101", "units": 3,
            "score": 76, "grade": "A", "raw_result": "76A"}], "previous_gpa": 5,
        "current_gpa": 5, "current_session": "2026/2027", "current_semester": "Harmattan", "cgpa": 5,
        "special_elective_units_outstanding": 0, "used_semester_ratio": "", "cumulative_remark": "Passed",
        "notices": [], "source_page": 1, "source_table": 1}


def nested_csv(record=None):
    record = record or source_record()
    row = {key: json.dumps(value) if key in {"current_courses", "outstanding_courses", "notices"} else value for key, value in record.items()}
    return ("\ufeff" + csv_text(CSV_FIELDS, [row])).encode("utf-8")


def raw_row():
    return ["1", "1", "1", "SYNTHETIC/2026/001", "EEE101\n(3)\n76A", "Passed", "",
        "3", "15", "5.00", "3", "15", "5.00", "6", "30", "5.00", "Passed", "SYNTHETIC/2026/001"]


def native_pdf(*, page_count=1, blank=False):
    """Small, real text/vector PDF; no external fixture or reportlab dependency."""
    def literal(value):
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands = ["0.5 w"]
    for x in range(30, 1631, 100):
        commands.append(f"{x} 710 m {x} 900 l S")
    for y in (710, 810, 840, 900):
        commands.append(f"30 {y} m 1630 {y} l S")
    def text(x, y, value, size=6):
        if not blank:
            commands.append(f"BT /F1 {size} Tf {x} {y} Td ({literal(value)}) Tj ET")
    text(30, 950, "SYNTHETIC - 2026/2027 HARMATTAN SEMESTER EXAMINATION RESULTS", 12)
    for index, value in enumerate(MAIN_HEADER):
        text(33 + index * 100, 870, value)
    for index, value in enumerate(SUBHEADER):
        text(33 + index * 100, 825, value)
    for index, value in enumerate(raw_row()[2:]):
        for line, part in enumerate(value.splitlines()):
            text(33 + index * 100, 790 - line * 15, part)
    content = ("\n".join(commands) + "\n").encode("ascii")
    kids = " ".join(f"{5 + index} 0 R" for index in range(page_count))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream"]
    for _ in range(page_count):
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1660 1000] /Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>")
    pdf, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(pdf)


class SourcePreparationTests(SimpleTestCase):
    def test_actual_nested_converter_csv_schema_bom_and_decimal_marks(self):
        data = nested_csv(source_record([{"course_code": "EEE101", "units": 3, "score": 77.5, "grade": "A", "raw_result": "77.5A"}]))
        result = prepare_source(data, "sample_students.csv", attempt_number=1)
        self.assertEqual(result["format"], "student_records_csv")
        self.assertEqual(result["summary"], {"source_course_rows": 1, "accepted_rows": 1, "unresolved_rows": 0})
        row, = csv.DictReader(io.StringIO(result["csv_text"]))
        self.assertEqual(row["identifier_value"], "SYNTHETIC/2026/001")
        self.assertEqual(row["score"], "77.50")
        self.assertEqual(result["trace"][0]["source_page"], "1")
        self.assertEqual(result["source_sha256"], hashlib.sha256(data).hexdigest())

    def test_raw_table_csv_uses_existing_parser_and_explicit_context(self):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerows([["source_page", "source_table"] + MAIN_HEADER, ["1", "1"] + SUBHEADER, raw_row()])
        data = output.getvalue().encode()
        with self.assertRaisesRegex(PreparationError, "reviewed academic_session"):
            prepare_source(data, "sample_tables.csv", attempt_number=1)
        result = prepare_source(data, "sample_tables.csv", attempt_number=1, academic_session="2026/2027", semester="harmattan")
        self.assertEqual(result["format"], "master_tables_csv")
        self.assertEqual(result["summary"]["accepted_rows"], 1)
        self.assertEqual(result["reviewed_context"]["context_source"], "reviewer")

    def test_canonical_csv_preserves_original_bom_line_endings_and_hash(self):
        row = {"identifier_type": "matriculation", "identifier_value": "000123", "course_code": "EEE101",
            "academic_session": "2026/2027", "semester": "harmattan", "attempt_number": "1", "score": "0.00"}
        text = "\ufeff" + csv_text(RESULT_COLUMNS, [row])
        data = text.encode()
        result = prepare_source(data, "ready.csv")
        self.assertEqual(result["format"], "canonical_csv")
        self.assertEqual(result["csv_text"], text)
        self.assertEqual(result["source_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(result["summary"]["accepted_rows"], 1)

    def test_zero_review_never_turns_undecided_ng_into_a_score(self):
        courses = [{"course_code": "EEE101", "score": 0, "grade": "F", "raw_result": "0F"},
            {"course_code": "EEE102", "score": 0, "grade": "NG", "raw_result": "0NG"}]
        data = nested_csv(source_record(courses))
        first = prepare_source(data, "sample_students.csv", attempt_number=1)
        self.assertEqual(first["summary"]["accepted_rows"], 0)
        reviewed = prepare_source(data, "sample_students.csv", attempt_number=1, include_reviewed_zero_scores=True)
        self.assertEqual(reviewed["summary"], {"source_course_rows": 2, "accepted_rows": 1, "unresolved_rows": 1})
        self.assertEqual(reviewed["issues"][0]["code"], "unresolved_mark")
        self.assertNotIn("EEE102", reviewed["csv_text"])

    def test_converter_attempt_and_source_context_are_not_guessed_or_overridden(self):
        with self.assertRaisesRegex(PreparationError, "attempt_number"):
            prepare_source(nested_csv(), "sample_students.csv")
        with self.assertRaisesRegex(PreparationError, "conflicts"):
            prepare_source(nested_csv(), "sample_students.csv", attempt_number=1, academic_session="2026/2027", semester="rain")

    def test_native_pdf_real_extraction_in_isolated_worker(self):
        result = prepare_source(native_pdf(), "native.pdf", attempt_number=1)
        self.assertEqual(result["format"], "master_sheet_pdf")
        self.assertEqual(result["summary"]["accepted_rows"], 1)
        self.assertEqual(result["trace"][0]["source_page"], 1)
        row, = csv.DictReader(io.StringIO(result["csv_text"]))
        self.assertEqual(row, {"identifier_type": "matriculation", "identifier_value": "SYNTHETIC/2026/001",
            "course_code": "EEE101", "academic_session": "2026/2027", "semester": "harmattan",
            "attempt_number": "1", "score": "76.00"})
        self.assertEqual(result["reviewed_context"]["context_source"], "source")

    def test_pdf_bounds_corruption_missing_text_and_conflicting_context_fail_safely(self):
        for data, options, message in (
            (b"%PDF-1.4\nprivate-raw-value", {}, "corrupted"),
            (native_pdf(blank=True), {}, "no selectable text"),
            (native_pdf(page_count=21), {}, "1 to 20 pages"),
            (native_pdf(), {"academic_session": "2026/2027", "semester": "rain"}, "conflicts"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(PreparationError, message) as caught:
                prepare_source(data, "source.pdf", attempt_number=1, **options)
            self.assertNotIn("private-raw-value", str(caught.exception))

    def test_upload_and_expanded_course_bounds_and_deep_json_are_rejected(self):
        with self.assertRaisesRegex(PreparationError, "2 MiB"):
            prepare_source(b"x" * (2 * 1024 * 1024 + 1), "source.csv")
        courses = [source_record()["current_courses"][0]] * 1001
        with self.assertRaisesRegex(PreparationError, "1000 source course"):
            prepare_source(nested_csv(source_record(courses)), "source.csv", attempt_number=1)
        record = source_record()
        row = {key: json.dumps(value) if key in {"current_courses", "outstanding_courses", "notices"} else value for key, value in record.items()}
        row["current_courses"] = "[" * 20000 + "0" + "]" * 20000
        with self.assertRaisesRegex(PreparationError, "invalid JSON"):
            prepare_source(csv_text(CSV_FIELDS, [row]).encode(), "source.csv", attempt_number=1)

    def test_unknown_header_has_expected_detected_schema_diagnostic(self):
        with self.assertRaisesRegex(PreparationError, "Detected columns: name, score"):
            prepare_source(b"name,score\nExample,75\n", "source.csv")


@override_settings(CURRENT_ACADEMIC_SESSION="2026/2027")
class PrepareEndpointTests(ImportFixture, TestCase):
    def upload(self, user=None, data=None, **options):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        file = SimpleUploadedFile("sample_students.csv", data or nested_csv(), content_type="text/csv")
        return client.post("/api/imports/prepare/", {"file": file, **options}, format="multipart")

    def test_preparation_writes_no_batch_student_result_or_audit(self):
        from students.models import Student
        from academics.models import Result
        before = (Student.objects.count(), Result.objects.count(), ImportBatch.objects.count(), ImportChange.objects.count())
        response = self.upload(self.hod, attempt_number=1)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["format"], "student_records_csv")
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertEqual(before, (Student.objects.count(), Result.objects.count(), ImportBatch.objects.count(), ImportChange.objects.count()))

    def test_permissions_and_active_assignment_checked_before_preparation(self):
        with patch("record_imports.views.prepare_source") as preparation:
            self.assertEqual(self.upload().status_code, 403)
            self.assignment.is_active = False
            self.assignment.save(update_fields=["is_active"])
            self.assertEqual(self.upload(self.staff, attempt_number=1).status_code, 403)
            preparation.assert_not_called()

    def test_missing_attempt_and_bad_nested_source_return_useful_400(self):
        response = self.upload(self.hod)
        self.assertEqual(response.status_code, 400)
        self.assertIn("attempt_number", str(response.data))
        response = self.upload(self.hod, data=b"unknown,header\n1,2\n", attempt_number=1)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Detected columns", str(response.data))

    def test_bounded_json_parser_rejects_deep_json_without_500(self):
        client = APIClient()
        client.force_authenticate(self.hod)
        response = client.post("/api/imports/previews/", data="[" * 2000 + "0" + "]" * 2000, content_type="application/json")
        self.assertEqual(response.status_code, 400)
