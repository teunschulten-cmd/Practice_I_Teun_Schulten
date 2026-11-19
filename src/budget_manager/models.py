"""Transaction domain model.

Every transaction has the same six fields, and all of them are always
present. Validation lives in validation.py and runs at construction
time so an invalid Transaction cannot be created.
"""

from budget_manager.validation import validate_transaction_fields


class Transaction:
    """One income or expense record."""

    def __init__(self, id, date, kind, category, amount, currency):
        # Validate at construction, then store the cleaned values.
        data = validate_transaction_fields(
            {
                "id": id,
                "date": date,
                "kind": kind,
                "category": category,
                "amount": amount,
                "currency": currency,
            }
        )
        self.id = data["id"]
        self.date = data["date"]
        self.kind = data["kind"]
        self.category = data["category"]
        self.amount = data["amount"]
        self.currency = data["currency"]

    def to_dict(self):
        """Return a JSON-friendly dictionary with every field present."""
        return {
            "id": self.id,
            "date": self.date,
            "kind": self.kind,
            "category": self.category,
            "amount": self.amount,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data):
        """Build a Transaction from a dictionary (file or CSV row)."""
        if not isinstance(data, dict):
            raise TypeError("Transaction data must be a dictionary.")
        return cls(
            id=data.get("id"),
            date=data.get("date"),
            kind=data.get("kind"),
            category=data.get("category"),
            amount=data.get("amount"),
            currency=data.get("currency"),
        )

    def __repr__(self):
        return (
            f"Transaction(id={self.id!r}, date={self.date!r}, "
            f"kind={self.kind!r}, category={self.category!r}, "
            f"amount={self.amount!r}, currency={self.currency!r})"
        )

    def __eq__(self, other):
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.to_dict() == other.to_dict()
