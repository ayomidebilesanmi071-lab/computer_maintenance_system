"""Reusable value coercion/validation helpers for the service layer.

The web forms already hand the services real ``date`` objects, but the same
services are also called from the seeding scripts, the command line and the
test-suite, where dates often arrive as ISO-8601 strings.  Coercing them here
means a malformed value is always rejected with the same friendly message
instead of raising a raw ``TypeError`` deep inside the logic.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from services.errors import ValidationError


def coerce_date(value, label: str = "Date"):
    """Return a ``datetime.date`` from a date/datetime/ISO string.

    ``None`` and blank strings return ``None`` so callers can apply their own
    default.  Anything else raises :class:`~services.errors.ValidationError`.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValidationError(
        f"{label} is not a valid date. Use the format YYYY-MM-DD.",
        {label: "Invalid date."},
    )


def coerce_decimal(value, label: str = "Amount", minimum=None):
    """Return a ``Decimal`` (or ``None``) and enforce an optional minimum."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError(
            f"{label} must be a number.", {label: "Enter a valid amount."}
        )
    if minimum is not None and number < minimum:
        raise ValidationError(
            f"{label} cannot be less than {minimum}.", {label: f"Minimum {minimum}."}
        )
    return number


def coerce_int(value, label: str = "Value"):
    """Return an ``int`` or ``None`` for blank input."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number.")
