"""Source evidence and non-blocking comparisons using the established weighted calculator.

Interim comparison convention (not institutional policy): two decimal places,
ROUND_HALF_UP, no tolerance. Missing/unverified history is explicitly labelled.
No endpoint resolves or edits these immutable source observations.
"""
from copy import copy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re

from django.core.exceptions import ValidationError
from django.db.models import Q

from academics.calculations import calculate_weighted_average
from academics.models import Result
from students.identity import identifier_key

from .student_sheet import CSV_FIELDS


def number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,8})?", str(value)):
        raise ValidationError("Reported averages must be nonnegative finite decimals or missing; no score is inferred.")
    try:
        return str(Decimal(str(value)))
    except InvalidOperation:
        raise ValidationError("Invalid reported average.") from None


def validate_source_context(context, kind, rows):
    if context in (None, {}):
        return {}
    if kind != "results" or not isinstance(context, dict) or set(context) != {"format", "source_sha256", "csv_sha256", "records"}:
        raise ValidationError("Source context requires format, source_sha256, csv_sha256 and records for results only.")
    if not isinstance(context["format"], str) or context["format"] not in {"master_sheet_pdf", "master_tables_csv", "student_records_csv"}:
        raise ValidationError("Unsupported source context format.")
    for key in ("source_sha256", "csv_sha256"):
        if not isinstance(context[key], str) or not re.fullmatch(r"[0-9a-f]{64}", context[key]):
            raise ValidationError("Source context hashes must be SHA-256 hexadecimal values.")
    records = context["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= 1000:
        raise ValidationError("Source context requires 1 to 1000 student-period records.")
    # Only bounded, JSON-safe evidence with the parser's documented fields survives.
    try:
        if len(json.dumps(context, allow_nan=False).encode()) > 2 * 1024 * 1024:
            raise ValueError()
    except (ValueError, TypeError, RecursionError):
        raise ValidationError("Source context must be finite JSON within 2 MiB.") from None
    allowed = set(CSV_FIELDS)
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != allowed:
            raise ValidationError("Source records must preserve the documented converter fields.")
        if not isinstance(record["matric_number"], str) or not record["matric_number"].strip() or len(record["matric_number"]) > 100:
            raise ValidationError("Source record requires a textual matriculation number.")
        session, semester = record["current_session"], record["current_semester"]
        if not isinstance(session, str) or not re.fullmatch(r"[0-9]{4}/[0-9]{4}", session) or not isinstance(semester, str) or semester not in {"harmattan", "rain"}:
            raise ValidationError("Source record requires its own academic session and semester.")
        key = (identifier_key(record["matric_number"]), session, semester)
        if key in seen:
            raise ValidationError("Repeated student-period source record.")
        seen.add(key)
        for field in ("current_gpa", "previous_gpa", "cgpa"):
            record[field] = number(record[field])
        for field in ("semester_remark", "cumulative_remark", "used_semester_ratio"):
            if record[field] is not None and (not isinstance(record[field], str) or len(record[field]) > 4000):
                raise ValidationError("Source remarks and ratio must be bounded source text.")
        for field in ("source_page", "source_table"):
            if record[field] not in (None, "") and (isinstance(record[field], bool) or not re.fullmatch(r"[1-9][0-9]{0,5}", str(record[field]))):
                raise ValidationError("Source page/table must be positive integer references or missing.")
        if not isinstance(record["current_courses"], list) or len(record["current_courses"]) > 1000:
            raise ValidationError("Invalid source course evidence.")
    # Every staged result must be bound to its own source student and period.
    from .mark_sheet_export import flatten
    try:
        accepted, _, _, _ = flatten(records, attempt_number=1, include_reviewed_zero_scores=True)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        raise ValidationError("Source course evidence is malformed.") from None
    source_scores = {(identifier_key(r["identifier_value"]), r["academic_session"], r["semester"], r["course_code"]): r["score"] for r in accepted}
    for row in rows:
        if row["identifier_type"] != "matriculation" or (identifier_key(row["identifier_value"]), row["academic_session"], row["semester"]) not in seen:
            raise ValidationError("Prepared results do not match the source student/period context.")
        score = source_scores.get((identifier_key(row["identifier_value"]), row["academic_session"], row["semester"], row["course_code"]))
        try:
            agrees = score is not None and Decimal(score) == Decimal(row["score"])
        except InvalidOperation:
            agrees = False
        if not agrees:
            raise ValidationError("Prepared scores must agree with literal resolved source marks; NG/missing marks cannot become scores.")
    return context


def metric(reported, calculated):
    reported = number(reported)
    if reported is None:
        return {"reported": None, "calculated": calculated, "difference": None, "status": "not_reported"}
    if calculated is None:
        return {"reported": reported, "calculated": None, "difference": None, "status": "not_comparable"}
    difference = Decimal(calculated) - Decimal(reported).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    return {"reported": reported, "calculated": calculated, "difference": str(difference),
        "status": "different" if difference else "matching"}


def compare(student, academic_session, semester, reported, *, proposed=()):
    # Same period for GPA, all attempts through that period for CGPA. Future
    # attempts cannot contaminate a comparison with an older source report.
    history = list(Result.objects.filter(student=student).filter(
        Q(offering__academic_session__name__lt=academic_session) |
        Q(offering__academic_session__name=academic_session,
          offering__semester__in=(["harmattan"] if semester == "harmattan" else ["harmattan", "rain"]))
    ).select_related("offering__academic_session", "grading_scale").order_by("pk"))
    inputs = [{"id": r.pk, "score": str(r.score), "verified": r.is_verified,
               "units": r.credit_units, "scale": r.grading_scale_id,
               "bands": r.grading_scale.bands if r.grading_scale else None, "offering": r.offering_id,
               "attempt": r.attempt_number} for r in history]
    for result in proposed:
        history = [r for r in history if (r.offering_id, r.attempt_number) != (result.offering_id, result.attempt_number)]
        history.append(result)
    def average(rows):
        try:
            value = calculate_weighted_average(rows)
            return None if value is None else str(value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
        except ValidationError:
            return None
    gpa = average([r for r in history if r.offering.academic_session.name == academic_session and r.offering.semester == semester])
    cgpa = average(history)
    return {"gpa": metric(reported.get("current_gpa"), gpa), "cgpa": metric(reported.get("cgpa"), cgpa),
        "previous_reported_gpa": number(reported.get("previous_gpa")),
        "previous_gpa_comparison": "not_compared_no_previous_period_binding",
        "calculation_basis": "proposed_scores_not_yet_verified" if proposed else "verified_recorded_results",
        "history_completeness": "not_established", "comparison_rule": "two_decimal_half_up_zero_tolerance_v1",
        "review_status": "unresolved", "blocking": False, "inputs": inputs}


def preview_performance(context, rows):
    if not context:
        return []
    from academics.models import CourseOffering
    from students.models import Student
    output = []
    for source in context["records"]:
        matched = [r for r in rows if r.get("student_id") and identifier_key(r["identifier_value"]) == identifier_key(source["matric_number"])
                   and r["academic_session"] == source["current_session"] and r["semester"] == source["current_semester"]]
        if not matched or any(r["action"] == "blocked" for r in matched):
            continue
        student = Student.objects.get(pk=matched[0]["student_id"])
        proposed = []
        for row in matched:
            # Preview only: the existing calculator receives projected verified
            # objects, while database results remain unverified until verification.
            offering = CourseOffering.objects.select_related("academic_session", "grading_scale").get(pk=row["offering_id"])
            existing = Result.objects.filter(student=student, offering=offering, attempt_number=int(row["attempt_number"])).first()
            projected = copy(existing) if existing else Result(student=student, offering=offering,
                attempt_number=int(row["attempt_number"]), credit_units=offering.credit_units, grading_scale=offering.grading_scale)
            projected.score = Decimal(row["score"])
            projected.is_verified = True
            proposed.append(projected)
        output.append({"student_id": str(student.pk), "academic_session": source["current_session"],
            "semester": source["current_semester"], "source": source,
            "comparison": compare(student, source["current_session"], source["current_semester"], source, proposed=proposed)})
    return output


def source_reports(student, academic_session=None, semester=None):
    rows = student.source_performances.select_related("batch", "academic_session").order_by("-created_at", "-pk")
    if academic_session is not None:
        rows = rows.filter(academic_session=academic_session, semester=semester)
    return [{"id": r.pk, "academic_session": r.academic_session.name, "semester": r.semester,
        "source": {key: value for key, value in r.source.items() if key not in {"matric_number", "current_courses", "outstanding_courses"}},
        "source_sha256": r.batch.source_context["source_sha256"], "format": r.batch.source_context["format"],
        "review_status": r.review_status, "comparison_at_import": {k: v for k, v in r.comparison_at_import.items() if k != "inputs"},
        "comparison": {k: v for k, v in compare(student, r.academic_session.name, r.semester, r.source).items() if k != "inputs"}}
        for r in rows]
