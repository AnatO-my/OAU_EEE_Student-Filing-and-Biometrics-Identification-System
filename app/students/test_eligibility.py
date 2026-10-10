from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .eligibility import validate_graduation_cgpa


class GraduationCGPATests(SimpleTestCase):
    def test_exactly_one_qualifies(self):
        validate_graduation_cgpa(Decimal("1.00"))

    def test_above_one_qualifies(self):
        validate_graduation_cgpa(Decimal("1.01"))

    def test_below_one_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_graduation_cgpa(Decimal("0.99"))

    def test_missing_or_invalid_cgpa_is_rejected(self):
        for value in [
            None,
            "1.00",
            Decimal("NaN"),
            Decimal("Infinity"),
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_graduation_cgpa(value)
