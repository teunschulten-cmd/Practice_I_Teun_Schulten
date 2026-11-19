# Run this program from the project root. For example:
#   PYTHONPATH=src python -m budget_manager add --date 2026-09-04 --kind expense --category food --amount 18.50 --currency EUR
#   PYTHONPATH=src python -m budget_manager list
#   PYTHONPATH=src python -m budget_manager report
#   PYTHONPATH=src python -m budget_manager import data/sample_transactions.csv
#   PYTHONPATH=src python -m budget_manager undo
#   PYTHONPATH=src python -m budget_manager interactive
#   PYTHONPATH=src python -m budget_manager --help
#
# The default data file is transactions.json in the current folder.
# Every change (add, import, undo, load) is saved immediately.
# The interactive command keeps a menu loop so you can add more than
# one entry without restarting the program.

"""Command-line interaction. This module has no business rules."""

import argparse
import sys
from pathlib import Path

from budget_manager import services, storage
from budget_manager.services import BudgetError
from budget_manager.storage import StorageError
from budget_manager.validation import ALLOWED_CATEGORIES, ValidationError

DEFAULT_FILE = "transactions.json"


def build_parser():
    """Create the argparse parser and all subcommands."""
    parser = argparse.ArgumentParser(
        description="Interactive Personal Budget Manager (Release 1).",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_FILE,
        help=f"JSON data file (default: {DEFAULT_FILE})",
    )

    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Add one income or expense.")
    add.add_argument("--date", required=True, help="ISO date, e.g. 2026-09-04")
    add.add_argument("--kind", required=True, choices=["expense", "income"])
    add.add_argument("--category", required=True, help="One of the allowed categories")
    add.add_argument("--amount", required=True, help="Positive number, e.g. 18.50")
    add.add_argument("--currency", required=True, help="3-letter ISO code, e.g. EUR")

    list_cmd = commands.add_parser("list", help="List stored transactions.")
    list_cmd.add_argument("--kind", choices=["expense", "income"])
    list_cmd.add_argument("--category", help="Filter by category")

    commands.add_parser("report", help="Show totals and a category breakdown.")

    save = commands.add_parser(
        "save",
        help="Copy the current data to another JSON file (refuses to overwrite unless --force).",
    )
    save.add_argument("destination")
    save.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination if it already exists.",
    )

    load = commands.add_parser("load", help="Replace the current data with a JSON file.")
    load.add_argument("source")

    import_csv = commands.add_parser(
        "import",
        help="Import transactions from a CSV file. Invalid rows are reported.",
    )
    import_csv.add_argument("source")

    commands.add_parser("undo", help="Remove the last transaction and save.")

    commands.add_parser(
        "interactive",
        help="Menu loop: add, list, report, or undo without restarting.",
    )

    return parser


def main(argv=None):
    """Parse the command, call the service layer, and print the result."""
    parser = build_parser()
    args = parser.parse_args(argv)
    data_file = Path(args.file)

    try:
        status = _run_command(args, data_file)
    except (ValidationError, BudgetError, StorageError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return status or 0


def _run_command(args, data_file):
    # Interactive mode has its own loop and loads the file itself.
    if args.command == "interactive":
        return run_interactive(data_file)

    # load_json returns an empty list when the file does not exist yet.
    transactions = storage.load_json(data_file)

    if args.command == "add":
        item = services.add_transaction(
            transactions,
            date=args.date,
            kind=args.kind,
            category=args.category,
            amount=args.amount,
            currency=args.currency,
        )
        storage.save_json(data_file, transactions)
        print(f"Added {item.id}.")

    elif args.command == "list":
        visible = services.list_transactions(
            transactions,
            kind=args.kind,
            category=args.category,
        )
        if not visible:
            print("No transactions to show.")
            return
        for item in visible:
            print(_format_transaction(item))

    elif args.command == "report":
        print(_format_report(services.summarize(transactions)))

    elif args.command == "save":
        storage.save_json(
            args.destination,
            transactions,
            overwrite=args.force,
        )
        print(f"Saved {len(transactions)} transaction(s) to {args.destination}.")

    elif args.command == "load":
        loaded = storage.load_json(args.source)
        storage.save_json(data_file, loaded)
        print(f"Loaded {len(loaded)} transaction(s) from {args.source}.")

    elif args.command == "import":
        imported, errors = services.import_csv(transactions, args.source)
        # Save after a partial import so valid rows are not lost.
        storage.save_json(data_file, transactions)
        print(f"Imported {imported} transaction(s).", flush=True)
        for message in errors:
            print(message, file=sys.stderr)
        if errors:
            return 1

    elif args.command == "undo":
        removed = services.undo_last(transactions)
        storage.save_json(data_file, transactions)
        print(f"Undone {removed.id}.")


MENU_TEXT = """1) Add transaction
2) List transactions
3) Report
4) Undo last
q) Quit"""


def run_interactive(data_file, input_func=input, output_func=print):
    """Run the menu loop until the user types q (or input ends).

    input_func and output_func can be replaced in tests so we do not
    have to type at a real terminal.
    """
    data_file = Path(data_file)
    try:
        transactions = storage.load_json(data_file)
    except StorageError as exc:
        output_func(f"Error: {exc}")
        return 1

    while True:
        output_func("")
        output_func(MENU_TEXT)
        try:
            choice = input_func("Choose an option: ").strip().lower()
            if choice == "q":
                output_func("Goodbye.")
                return 0
            elif choice == "1":
                _interactive_add(transactions, data_file, input_func, output_func)
            elif choice == "2":
                _interactive_list(transactions, output_func)
            elif choice == "3":
                output_func(_format_report(services.summarize(transactions)))
            elif choice == "4":
                _interactive_undo(transactions, data_file, output_func)
            else:
                output_func("Unknown option, choose 1-4 or q.")
        except EOFError:
            # End of input (Ctrl+D, or a test that runs out of lines).
            output_func("Goodbye.")
            return 0


def _interactive_add(transactions, data_file, input_func, output_func):
    """Ask for the six fields, then reuse services.add_transaction."""
    categories = ", ".join(ALLOWED_CATEGORIES)
    date = input_func("Date (YYYY-MM-DD): ").strip()
    kind = input_func("Kind (expense or income): ").strip()
    category = input_func(f"Category ({categories}): ").strip()
    amount = input_func("Amount: ").strip()
    currency = input_func("Currency (e.g. EUR): ").strip()

    try:
        item = services.add_transaction(
            transactions,
            date=date,
            kind=kind,
            category=category,
            amount=amount,
            currency=currency,
        )
        storage.save_json(data_file, transactions)
        output_func(f"Added {item.id}.")
    except (ValidationError, BudgetError, StorageError) as exc:
        # Show the same clear message and go back to the menu.
        # The value is not changed or stored.
        output_func(f"Error: {exc}")


def _interactive_list(transactions, output_func):
    visible = services.list_transactions(transactions)
    if not visible:
        output_func("No transactions to show.")
        return
    for item in visible:
        output_func(_format_transaction(item))


def _interactive_undo(transactions, data_file, output_func):
    try:
        removed = services.undo_last(transactions)
        storage.save_json(data_file, transactions)
        output_func(f"Undone {removed.id}.")
    except (BudgetError, StorageError) as exc:
        output_func(f"Error: {exc}")


def _format_transaction(item):
    """Format one transaction as a single aligned line."""
    return (
        f"{item.id}  {item.date}  {item.kind:<7}  "
        f"{item.category:<13}  {item.amount:>10.2f} {item.currency}"
    )


def _format_report(summary):
    """Turn the summarize() result into readable text. No calculations here."""
    lines = [f"Transactions: {summary['count']}"]
    by_currency = summary["by_currency"]
    if not by_currency:
        lines.append("No transactions to report.")
        return "\n".join(lines)

    for currency in sorted(by_currency):
        bucket = by_currency[currency]
        lines.append("")
        lines.append(f"Currency: {currency}")
        lines.append(f"  Income:  {bucket['income']:.2f}")
        lines.append(f"  Expense: {bucket['expense']:.2f}")
        lines.append(f"  Balance: {bucket['balance']:.2f}")
        lines.append("  By category:")
        # Largest absolute impact first, then name, so the report is stable.
        categories = sorted(
            bucket["by_category"].items(),
            key=lambda pair: (-abs(pair[1]), pair[0]),
        )
        for name, total in categories:
            lines.append(f"    {name:<15} {total:+.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
