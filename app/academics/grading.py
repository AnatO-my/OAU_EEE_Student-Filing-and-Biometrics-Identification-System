from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


INITIAL_BANDS = [
    {"minimum": "0", "maximum": "40", "grade_point": "0"},
    {"minimum": "40", "maximum": "45", "grade_point": "1"},
    {"minimum": "45", "maximum": "50", "grade_point": "2"},
    {"minimum": "50", "maximum": "60", "grade_point": "3"},
    {"minimum": "60", "maximum": "70", "grade_point": "4"},
    {"minimum": "70", "maximum": "100", "grade_point": "5"},
]


def validate_bands(bands):
    if not isinstance(bands, list) or not bands:
        raise ValidationError({"bands": "Provide the complete list of grading bands."})
    parsed = []
    for band in bands:
        if not isinstance(band, dict) or set(band) != {"minimum", "maximum", "grade_point"}:
            raise ValidationError({"bands": "Each band needs minimum, maximum and grade_point."})
        try:
            values = tuple(Decimal(str(band[key])) for key in ("minimum", "maximum", "grade_point"))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError({"bands": "Band values must be decimal numbers."})
        if any(not value.is_finite() for value in values):
            raise ValidationError({"bands": "Band values must be finite."})
        minimum, maximum, points = values
        if not (Decimal("0") <= minimum < maximum <= Decimal("100")):
            raise ValidationError({"bands": "Use increasing score limits within 0..100."})
        if not (Decimal("0") <= points <= Decimal("5")) or points != points.to_integral_value():
            raise ValidationError({"bands": "Grade points must be integers from 0 to 5."})
        if any(value != value.quantize(Decimal("0.01")) for value in (minimum, maximum)):
            raise ValidationError({"bands": "Score boundaries allow at most two decimal places."})
        parsed.append(values)
    parsed.sort(key=lambda values: values[0])
    expected = Decimal("0")
    for minimum, maximum, points in parsed:
        if minimum != expected:
            raise ValidationError({"bands": "Bands must cover 0..100 without overlaps or gaps."})
        expected = maximum
    if expected != Decimal("100"):
        raise ValidationError({"bands": "Bands must end at 100."})
    return parsed


def validate_score(score):
    if not isinstance(score, Decimal) or not score.is_finite():
        raise ValidationError({"score": "Provide a finite Decimal score."})
    if not Decimal("0") <= score <= Decimal("100"):
        raise ValidationError({"score": "Score must be between 0 and 100."})


def grade_point_for_score(score, *, grading_scale=None):
    validate_score(score)
    if grading_scale is not None and not grading_scale.is_published:
        raise ValidationError("Only published grading versions can calculate results.")
    bands = INITIAL_BANDS if grading_scale is None else grading_scale.bands
    for minimum, maximum, points in validate_bands(bands):
        if minimum <= score < maximum or score == maximum == Decimal("100"):
            return points
    raise ValidationError("No grading band matches this score.")
