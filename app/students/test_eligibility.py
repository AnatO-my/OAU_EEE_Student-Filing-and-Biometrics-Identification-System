from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .eligibility import validate_graduation_cgpa


# Cover the CGPA threshold and invalid-value rules for graduation.
class GraduationCGPATests(SimpleTestCase):
    # A finite CGPA exactly at the minimum is accepted.
    def test_exactly_one_qualifies(self):
        validate_graduation_cgpa(Decimal("1.00"))

    # A finite CGPA above the minimum is accepted.
    def test_above_one_qualifies(self):
        validate_graduation_cgpa(Decimal("1.01"))

    # CGPA below the graduation threshold is rejected.
    def test_below_one_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_graduation_cgpa(Decimal("0.99"))

    # Missing, non-decimal, and non-finite values cannot qualify.
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
