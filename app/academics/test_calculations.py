from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .calculations import calculate_weighted_average


def make_result(score, units, verified=True):
    return SimpleNamespace(
        score=Decimal(score) if score is not None else None,
        credit_units=units,
        is_verified=verified,
    )


class WeightedAverageTests(SimpleTestCase):
    def test_courses_are_weighted_by_units(self):
        results = [
            make_result("70", 3),  # 5 × 3 = 15
            make_result("50", 2),  # 3 × 2 = 6
        ]

        self.assertEqual(
            calculate_weighted_average(results),
            Decimal("4.2"),  # 21 / 5
        )

    def test_failed_attempt_and_repeat_both_count(self):
        results = [
            make_result("30", 3),  # Failed attempt: 0 points
            make_result("70", 3),  # Repeat: 15 points
        ]

        self.assertEqual(
            calculate_weighted_average(results),
            Decimal("2.5"),  # 15 / 6
        )

    def test_no_results_returns_none(self):
        self.assertIsNone(calculate_weighted_average([]))

    def test_unverified_result_blocks_calculation(self):
        results = [
            make_result("70", 3),
            make_result("50", 2, verified=False),
        ]

        with self.assertRaises(ValidationError):
            calculate_weighted_average(results)

    def test_missing_score_blocks_calculation(self):
        with self.assertRaises(ValidationError):
            calculate_weighted_average([make_result(None, 3)])

    def test_invalid_units_are_rejected(self):
        for units in (0, -1, True, Decimal("3"), None):
            with self.subTest(units=units):
                with self.assertRaises(ValidationError):
                    calculate_weighted_average(
                        [make_result("70", units)]
                    )

    def test_average_below_one_is_not_rounded_up(self):
        results = [
            make_result("40", 199),
            make_result("0", 1),
        ]

        self.assertEqual(
            calculate_weighted_average(results),
            Decimal("0.995"),
        )