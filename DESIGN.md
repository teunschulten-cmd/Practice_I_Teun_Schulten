# Design rationale

Release 1 is built as four layers with a single direction of dependency:
the CLI parses arguments and prints text, services apply budget rules,
validation enforces the transaction contract, and storage only reads and
writes files. That split is the key architectural choice. It means a
test can add a transaction and check a report without going through
argparse, and the same validation function is used at construction, at
CSV import, and when a JSON file is reloaded — so a bad amount cannot
sneak in through one door and get rejected at another. Persistence
always uses a temporary file followed by `os.replace`, and every change
(including undo) is written immediately. Undo is therefore a change to
the file, not an in-memory trick: after a crash and a fresh load, the
last record on disk is still the one that undo will remove.

## Exit ticket

### What did you verify?

CSV import of `data/sample_transactions.csv` reports exactly
`Row 4: amount must be > 0.` for the third data row (a food expense of
-5.00), does not store that row, and still imports the five valid
rows (`T001`, `T002`, `T009`, `T010`, `T011`) with a EUR balance of
1829.10. That result is asserted in
`test_csv_import_reports_row_errors_and_keeps_valid_rows`.

### Which boundary changed your design?

Lowercase `eur` was the edge case that forced a change. An early
instinct was to normalise currency codes with `.upper()`, which would
have made the demo easier. The brief forbids silently correcting
ambiguous data, so `eur` is rejected with
`currency must be a 3-letter ISO code (e.g. EUR).` The same policy
applies to categories: `Food` or `snacks` is not rewritten as `food`.
Whitespace is still trimmed, because that is input cleaning, not a
guess about what the user meant.

### What would you refactor next?

In Release 2 I would add a date-range filter and a monthly budget cap
in `services.py` (for example `summarize(transactions, start, end)` and
a warning when food spending in a month exceeds a limit). The current
report is a full-history total only, which is enough to prove the core
but not very useful once the file grows.
