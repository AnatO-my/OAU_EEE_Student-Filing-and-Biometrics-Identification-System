from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .grading import grade_point_for_score


# Cover default scale boundary ownership and rejection of invalid score inputs.
class GradingTests(SimpleTestCase):
    # Check each grading transition and the inclusive maximum.
    def test_grade_boundaries(self):
        cases = [
            ("0", "0"),
            ("39.99", "0"),
            ("40", "1"),
            ("44.99", "1"),
            ("45", "2"),
            ("49.99", "2"),
            ("50", "3"),
            ("59.99", "3"),
            ("60", "4"),
            ("69.99", "4"),
            ("70", "5"),
            ("100", "5"),
        ]

        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(
                    grade_point_for_score(Decimal(score)),
                    Decimal(expected),
                )

    # Reject finite scores outside the 0–100 scale.
    def test_scores_outside_valid_range_are_rejected(self):
        for score in ("-0.01", "100.01"):
            with self.subTest(score=score):
                with self.assertRaises(ValidationError):
                    grade_point_for_score(Decimal(score))

    # Reject absent, non-Decimal, and non-finite scores.
    def test_missing_or_invalid_scores_are_rejected(self):
        for score in (
            None,
            "70",
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with self.subTest(score=score):
                with self.assertRaises(ValidationError):
                    grade_point_for_score(score)