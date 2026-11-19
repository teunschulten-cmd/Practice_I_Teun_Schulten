"""Domain rules and business logic for the budget manager.

This module is the only place that decides how transactions are added,
listed, summarised, imported, or undone. The CLI only collects input
and prints results.
"""

import csv
from pathlib import Path

from budget_manager.models import Transaction
from budget_manager.validation import ValidationError


class BudgetError(Exception):
    """A business-rule problem that the CLI can show to the user."""


def next_id(transactions):
    """Return the next unused id (T001, T002, ...) based on existing ids."""
    highest = 0
    for item in transactions:
        # IDs are already validated, so the part after T is an integer.
        number = int(item.id[1:])
        if number > highest:
            highest = number
    return f"T{highest + 1:03d}"


def add_transaction(transactions, date, kind, category, amount, currency, id=None):
    """Validate, assign an id if needed, append, and return the new record."""
    if id is None:
        id = next_id(transactions)
    else:
        _ensure_unique_id(transactions, id)

    transaction = Transaction(
        id=id,
        date=date,
        kind=kind,
        category=category,
        amount=amount,
        currency=currency,
    )
    # A second check covers the auto-generated id as well.
    _ensure_unique_id(transactions, transaction.id)
    transactions.append(transaction)
    return transaction


def list_transactions(transactions, kind=None, category=None):
    """Return transactions, optionally filtered by kind or category."""
    result = []
    for item in transactions:
        if kind is not None and item.kind != kind:
            continue
        if category is not None and item.category != category:
            continue
        result.append(item)
    return result


def summarize(transactions):
    """Compute counts, totals, and a per-category breakdown.

    Totals are grouped by currency so amounts in EUR and USD are never
    added together. Income is stored as a positive contribution to the
    balance; expenses are subtracted.
    """
    by_currency = {}
    for item in transactions:
        bucket = by_currency.setdefault(
            item.currency,
            {
                "income": 0.0,
                "expense": 0.0,
                "balance": 0.0,
                "by_category": {},
            },
        )
        if item.kind == "income":
            bucket["income"] += item.amount
            bucket["balance"] += item.amount
            signed = item.amount
        else:
            bucket["expense"] += item.amount
            bucket["balance"] -= item.amount
            signed = -item.amount
        categories = bucket["by_category"]
        categories[item.category] = categories.get(item.category, 0.0) + signed

    return {"count": len(transactions), "by_currency": by_currency}


def undo_last(transactions):
    """Remove and return the last transaction, or raise if the list is empty."""
    if not transactions:
        raise BudgetError("Nothing to undo.")
    return transactions.pop()


def import_csv(transactions, csv_path):
    """Import rows from a CSV file.

    Valid rows are appended. Invalid rows are not imported. Every bad
    row produces a message such as 'Row 4: amount must be > 0.'.
    Existing transactions are left as they are.

    Returns a tuple: (imported_count, list_of_error_messages).
    """
    path = Path(csv_path)
    try:
        # utf-8-sig quietly drops a BOM if Excel added one.
        handle = path.open(encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise BudgetError(f"Cannot open CSV file {path}: {exc.strerror or exc}.")

    imported = 0
    errors = []
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise BudgetError(f"CSV file {path} is empty or has no header row.")

        # Row 1 is the header, so the first data row is row 2.
        for row_number, row in enumerate(reader, start=2):
            try:
                cleaned = {key: (value if value is not None else "") for key, value in row.items()}
                candidate_id = str(cleaned.get("id", "")).strip()
                if candidate_id:
                    _ensure_unique_id(transactions, candidate_id)
                add_transaction(
                    transactions,
                    id=cleaned.get("id"),
                    date=cleaned.get("date"),
                    kind=cleaned.get("kind"),
                    category=cleaned.get("category"),
                    amount=cleaned.get("amount"),
                    currency=cleaned.get("currency"),
                )
                imported += 1
            except (ValidationError, BudgetError) as exc:
                errors.append(f"Row {row_number}: {exc}")

    return imported, errors


def _ensure_unique_id(transactions, tx_id):
    for item in transactions:
        if item.id == tx_id:
            raise BudgetError(f"duplicate id: {tx_id}.")
