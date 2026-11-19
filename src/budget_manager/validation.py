"""Boundary validation for transactions.

Rules are defined in one place so the CLI, CSV import, and file loading
all apply the same checks. Ambiguous values are rejected with a clear
message; they are never silently corrected.
"""

import re
from datetime import date


# Controlled vocabulary for categories. Unknown values are rejected
# (the defined policy), not mapped to a catch-all such as "other".
ALLOWED_CATEGORIES = (
    "education",
    "entertainment",
    "food",
    "freelance",
    "gift",
    "health",
    "rent",
    "salary",
    "shopping",
    "transport",
    "utilities",
)

ALLOWED_KINDS = ("expense", "income")

# T001, T002, ... — at least three digits after the letter T.
ID_PATTERN = re.compile(r"^T[0-9]{3,}$")

# Currency must already be a 3-letter uppercase ISO-style code.
# "eur" is not silently uppercased to "EUR".
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

# Date text must be exactly YYYY-MM-DD (not a more relaxed ISO variant).
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

REQUIRED_FIELDS = ("id", "date", "kind", "category", "amount", "currency")


class ValidationError(ValueError):
    """Raised when a transaction field does not meet the schema rules."""


def category_policy_message():
    """Explain the category policy in one sentence."""
    allowed = ", ".join(ALLOWED_CATEGORIES)
    return f"category must be one of: {allowed}."


def validate_transaction_fields(data):
    """Validate and clean a mapping of transaction fields.

    Returns a new dictionary with stripped strings and a float amount.
    Raises ValidationError on the first problem found. Whitespace around
    text is trimmed (input cleaning). Values are not otherwise rewritten.
    """
    if data is None or not isinstance(data, dict):
        raise ValidationError("transaction must be a set of named fields.")

    missing = [name for name in REQUIRED_FIELDS if _is_missing(data.get(name))]
    if missing:
        raise ValidationError(f"missing field: {missing[0]}.")

    tx_id = _as_text(data["id"], "id")
    if not ID_PATTERN.fullmatch(tx_id):
        raise ValidationError("id must match T followed by at least three digits (e.g. T001).")

    date_text = _as_text(data["date"], "date")
    if not DATE_PATTERN.fullmatch(date_text):
        raise ValidationError("date must be ISO format YYYY-MM-DD.")
    try:
        date.fromisoformat(date_text)
    except ValueError:
        raise ValidationError("date must be a real calendar date in ISO format YYYY-MM-DD.")

    kind = _as_text(data["kind"], "kind")
    if kind not in ALLOWED_KINDS:
        raise ValidationError("kind must be 'expense' or 'income'.")

    category = _as_text(data["category"], "category")
    if category not in ALLOWED_CATEGORIES:
        raise ValidationError(category_policy_message())

    amount = _as_amount(data["amount"])
    if amount <= 0:
        raise ValidationError("amount must be > 0.")

    currency = _as_text(data["currency"], "currency")
    if not CURRENCY_PATTERN.fullmatch(currency):
        raise ValidationError("currency must be a 3-letter ISO code (e.g. EUR).")

    return {
        "id": tx_id,
        "date": date_text,
        "kind": kind,
        "category": category,
        "amount": amount,
        "currency": currency,
    }


def _is_missing(value):
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _as_text(value, field_name):
    text = str(value).strip()
    if text == "":
        raise ValidationError(f"missing field: {field_name}.")
    return text


def _as_amount(value):
    """Parse amount without guessing at unusual number formats."""
    if isinstance(value, bool):
        # bool is a subclass of int, but True/False is not a useful amount.
        raise ValidationError("amount must be a number.")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        # Do not silently treat "18,50" as 18.50.
        if "," in text:
            raise ValidationError("amount must be a number (use a dot, not a comma).")
        try:
            number = float(text)
        except ValueError:
            raise ValidationError("amount must be a number.")
    if number != number:  # NaN
        raise ValidationError("amount must be a number.")
    return number
