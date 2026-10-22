from decimal import Decimal

from rest_framework.exceptions import ValidationError


# Reject graduation unless the calculated CGPA is finite and at least 1.00.
def validate_graduation_cgpa(cgpa):
    if (
        not isinstance(cgpa, Decimal)
        or not cgpa.is_finite()
    ):
        raise ValidationError({
            "academic_status": (
                "Graduation requires a verified, calculated CGPA."
            )
        })

    if cgpa < Decimal("1.00"):
        raise ValidationError({
            "academic_status": (
                "Graduation requires CGPA of at least 1.00."
            )
        })