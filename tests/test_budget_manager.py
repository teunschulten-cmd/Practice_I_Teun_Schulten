"""Tests for the budget manager: one normal case and several boundaries.

Run from the project root:

    python -m unittest discover -s tests -v
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# Make `import budget_manager` work when tests are launched from the
# project root or from this file, without requiring a package install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from budget_manager import services, storage
from budget_manager.cli import main, run_interactive
from budget_manager.services import BudgetError
from budget_manager.storage import StorageError
from budget_manager.validation import ValidationError

SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_transactions.csv"


class NormalCaseTests(unittest.TestCase):
    """Happy path: add valid transactions and compute a report."""

    def test_add_and_summarize_normal_case(self):
        transactions = []
        food = services.add_transaction(
            transactions,
            date="2026-09-04",
            kind="expense",
            category="food",
            amount=18.50,
            currency="EUR",
        )
        salary = services.add_transaction(
            transactions,
            date="2026-09-05",
            kind="income",
            category="salary",
            amount=2500.00,
            currency="EUR",
        )

        self.assertEqual(food.id, "T001")
        self.assertEqual(salary.id, "T002")
        self.assertEqual(len(transactions), 2)

        summary = services.summarize(transactions)
        expected = {
            "count": 2,
            "by_currency": {
                "EUR": {
                    "income": 2500.00,
                    "expense": 18.50,
                    "balance": 2481.50,
                    "by_category": {
                        "food": -18.50,
                        "salary": 2500.00,
                    },
                }
            },
        }
        self.assertEqual(summary, expected)


class BoundaryTests(unittest.TestCase):
    """Edge cases and malformed input, with explicit expected messages."""

    def test_negative_amount_is_rejected(self):
        transactions = []
        with self.assertRaises(ValidationError) as ctx:
            services.add_transaction(
                transactions,
                date="2026-09-06",
                kind="expense",
                category="food",
                amount=-5,
                currency="EUR",
            )
        self.assertEqual(str(ctx.exception), "amount must be > 0.")
        self.assertEqual(transactions, [])

    def test_unknown_category_is_rejected(self):
        transactions = []
        with self.assertRaises(ValidationError) as ctx:
            services.add_transaction(
                transactions,
                date="2026-09-07",
                kind="expense",
                category="snacks",
                amount=9.00,
                currency="EUR",
            )
        expected = (
            "category must be one of: education, entertainment, food, "
            "freelance, gift, health, rent, salary, shopping, transport, "
            "utilities."
        )
        self.assertEqual(str(ctx.exception), expected)
        self.assertEqual(transactions, [])

    def test_lowercase_currency_is_not_silently_fixed(self):
        # "eur" must not be rewritten as "EUR".
        transactions = []
        with self.assertRaises(ValidationError) as ctx:
            services.add_transaction(
                transactions,
                date="2026-09-09",
                kind="expense",
                category="health",
                amount=45.00,
                currency="eur",
            )
        self.assertEqual(
            str(ctx.exception),
            "currency must be a 3-letter ISO code (e.g. EUR).",
        )
        self.assertEqual(transactions, [])

    def test_zero_amount_is_rejected(self):
        transactions = []
        with self.assertRaises(ValidationError) as ctx:
            services.add_transaction(
                transactions,
                date="2026-09-08",
                kind="expense",
                category="utilities",
                amount=0,
                currency="EUR",
            )
        self.assertEqual(str(ctx.exception), "amount must be > 0.")

    def test_invalid_date_is_rejected(self):
        transactions = []
        with self.assertRaises(ValidationError) as ctx:
            services.add_transaction(
                transactions,
                date="2026-13-01",
                kind="expense",
                category="rent",
                amount=900,
                currency="EUR",
            )
        self.assertEqual(
            str(ctx.exception),
            "date must be a real calendar date in ISO format YYYY-MM-DD.",
        )

    def test_csv_import_reports_row_errors_and_keeps_valid_rows(self):
        transactions = []
        imported, errors = services.import_csv(transactions, SAMPLE_CSV)

        self.assertEqual(imported, 5)
        self.assertEqual([item.id for item in transactions], ["T001", "T002", "T009", "T010", "T011"])
        self.assertEqual(
            errors,
            [
                "Row 4: amount must be > 0.",
                (
                    "Row 5: category must be one of: education, entertainment, "
                    "food, freelance, gift, health, rent, salary, shopping, "
                    "transport, utilities."
                ),
                "Row 6: date must be a real calendar date in ISO format YYYY-MM-DD.",
                "Row 7: kind must be 'expense' or 'income'.",
                "Row 8: amount must be > 0.",
                "Row 9: currency must be a 3-letter ISO code (e.g. EUR).",
            ],
        )

        summary = services.summarize(transactions)
        eur = summary["by_currency"]["EUR"]
        self.assertEqual(summary["count"], 5)
        self.assertAlmostEqual(eur["income"], 2800.00)
        self.assertAlmostEqual(eur["expense"], 970.90)
        self.assertAlmostEqual(eur["balance"], 1829.10)

    def test_mixed_currencies_are_not_added_together(self):
        transactions = []
        services.add_transaction(
            transactions, date="2026-09-04", kind="income",
            category="salary", amount=100, currency="EUR",
        )
        services.add_transaction(
            transactions, date="2026-09-04", kind="income",
            category="freelance", amount=50, currency="USD",
        )
        summary = services.summarize(transactions)
        self.assertEqual(summary["by_currency"]["EUR"]["income"], 100)
        self.assertEqual(summary["by_currency"]["USD"]["income"], 50)
        self.assertNotIn("total", summary)


class PersistenceTests(unittest.TestCase):
    """Save/load/undo must leave the file in a consistent state."""

    def test_undo_persists_after_reload(self):
        # If the process "crashes" and starts again, undo still applies
        # to the last transaction that was actually saved on disk.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "transactions.json"
            transactions = storage.load_json(path)
            services.add_transaction(
                transactions, date="2026-09-04", kind="expense",
                category="food", amount=18.50, currency="EUR",
            )
            services.add_transaction(
                transactions, date="2026-09-05", kind="income",
                category="salary", amount=2500.00, currency="EUR",
            )
            storage.save_json(path, transactions)

            # Simulate a crash and a fresh start: load from disk again.
            reloaded = storage.load_json(path)
            self.assertEqual([item.id for item in reloaded], ["T001", "T002"])

            removed = services.undo_last(reloaded)
            storage.save_json(path, reloaded)
            self.assertEqual(removed.id, "T002")

            after_undo = storage.load_json(path)
            self.assertEqual([item.id for item in after_undo], ["T001"])
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_undo_on_empty_list_is_rejected(self):
        with self.assertRaises(BudgetError) as ctx:
            services.undo_last([])
        self.assertEqual(str(ctx.exception), "Nothing to undo.")

    def test_save_replaces_the_target_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "transactions.json"
            transactions = []
            services.add_transaction(
                transactions, date="2026-09-04", kind="expense",
                category="food", amount=10, currency="EUR",
            )
            storage.save_json(path, transactions)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(raw), 1)
            self.assertEqual(raw[0]["id"], "T001")
            self.assertEqual(set(raw[0].keys()), {
                "id", "date", "kind", "category", "amount", "currency",
            })
            self.assertFalse(list(Path(folder).glob("*.tmp")))

    def test_save_to_existing_backup_is_rejected(self):
        # A second save must not silently replace the only backup copy.
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            store = folder / "transactions.json"
            backup = folder / "backup.json"

            transactions = []
            services.add_transaction(
                transactions, date="2026-09-04", kind="expense",
                category="food", amount=10, currency="EUR",
            )
            storage.save_json(store, transactions)
            storage.save_json(backup, transactions)
            original = backup.read_text(encoding="utf-8")

            services.add_transaction(
                transactions, date="2026-09-05", kind="income",
                category="salary", amount=2500, currency="EUR",
            )
            storage.save_json(store, transactions)

            with self.assertRaises(StorageError) as ctx:
                storage.save_json(backup, transactions, overwrite=False)
            self.assertIn("already exists", str(ctx.exception))
            self.assertEqual(backup.read_text(encoding="utf-8"), original)

            captured = io.StringIO()
            with redirect_stdout(captured), redirect_stderr(captured):
                status = main(["--file", str(store), "save", str(backup)])
            self.assertEqual(status, 1)
            self.assertIn("already exists", captured.getvalue())
            self.assertEqual(backup.read_text(encoding="utf-8"), original)

            captured = io.StringIO()
            with redirect_stdout(captured), redirect_stderr(captured):
                status = main(["--file", str(store), "save", str(backup), "--force"])
            self.assertEqual(status, 0)
            self.assertIn("Saved 2 transaction(s)", captured.getvalue())
            self.assertNotEqual(backup.read_text(encoding="utf-8"), original)
            self.assertEqual(
                [item.id for item in storage.load_json(backup)],
                ["T001", "T002"],
            )


class InteractiveTests(unittest.TestCase):
    """Menu loop: several entries in one session, without restarting."""

    def _answers(self, lines):
        """Return a fake input() that walks through the given replies."""
        remaining = iter(lines)

        def input_func(prompt=""):
            try:
                return next(remaining)
            except StopIteration:
                raise EOFError

        return input_func

    def test_interactive_add_rejects_negative_and_saves_one(self):
        # Valid expense, then a negative amount (rejected), then quit.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "transactions.json"
            replies = [
                "1",
                "2026-09-04",
                "expense",
                "food",
                "18.50",
                "EUR",
                "1",
                "2026-09-06",
                "expense",
                "food",
                "-5",
                "EUR",
                "q",
            ]
            output = []

            def output_func(text=""):
                output.append(str(text))

            status = run_interactive(
                path,
                input_func=self._answers(replies),
                output_func=output_func,
            )
            self.assertEqual(status, 0)
            self.assertIn("Added T001.", output)
            self.assertIn("Error: amount must be > 0.", output)

            saved = storage.load_json(path)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].id, "T001")
            self.assertEqual(saved[0].amount, 18.50)
            self.assertEqual(saved[0].category, "food")

    def test_interactive_unknown_option_message(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "transactions.json"
            output = []

            def output_func(text=""):
                output.append(str(text))

            status = run_interactive(
                path,
                input_func=self._answers(["5", "q"]),
                output_func=output_func,
            )
            self.assertEqual(status, 0)
            self.assertIn("Unknown option, choose 1-4 or q.", output)
            self.assertIn("Goodbye.", output)
            self.assertEqual(storage.load_json(path), [])


if __name__ == "__main__":
    unittest.main()
