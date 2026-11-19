"""Persistence and file I/O for transactions.

Save writes to a temporary file first and then replaces the target with
os.replace. That way a crash mid-write cannot leave a half-written JSON
file as the only copy on disk.
"""

import json
import os
from pathlib import Path

from budget_manager.models import Transaction
from budget_manager.validation import ValidationError


class StorageError(Exception):
    """Raised when a file cannot be read or written safely."""


def load_json(path):
    """Load a list of transactions from a JSON file.

    A missing file is treated as an empty list (first run). Invalid
    records are not skipped silently: loading stops with a clear error.
    """
    path = Path(path)
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StorageError(f"Cannot read {path}: {exc.strerror or exc}.")

    if text.strip() == "":
        return []

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StorageError(f"Cannot read {path}: file is not valid JSON ({exc.msg}).")

    if not isinstance(raw, list):
        raise StorageError(f"Cannot read {path}: expected a list of transactions.")

    transactions = []
    for index, row in enumerate(raw, start=1):
        try:
            transactions.append(Transaction.from_dict(row))
        except (ValidationError, TypeError) as exc:
            raise StorageError(f"Record {index} in {path}: {exc}")
    return transactions


def save_json(path, transactions, overwrite=True):
    """Write transactions to JSON using an atomic replace.

    The live data file uses overwrite=True (the default), so add, import,
    undo, and load can update it safely. Backups use overwrite=False: if
    the destination already exists, the call fails instead of destroying
    the only recovery copy. Use overwrite=True (--force in the CLI) to
    replace a backup on purpose.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(f"Cannot write {path}: {exc.strerror or exc}.")

    created_placeholder = False
    if not overwrite:
        try:
            # Exclusive create, same idea as open(..., "x") in the course
            # demo. The empty file is then replaced atomically below.
            with path.open("x", encoding="utf-8"):
                pass
            created_placeholder = True
        except FileExistsError:
            raise StorageError(
                f"Cannot save to {path}: file already exists. "
                "Choose a new name or use --force to overwrite it."
            )

    # A suffix on the full name works even when the file has several dots.
    temp_path = path.with_name(path.name + ".tmp")
    payload = [item.to_dict() for item in transactions]
    text = json.dumps(payload, indent=2) + "\n"

    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    except OSError as exc:
        # Best effort: do not leave a stray temp file or empty placeholder.
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        if created_placeholder and path.exists() and path.stat().st_size == 0:
            try:
                path.unlink()
            except OSError:
                pass
        raise StorageError(f"Cannot write {path}: {exc.strerror or exc}.")
