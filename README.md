# Personal Budget Manager — Release 1

Teun Schulten  
Master in Technology and Business — Programming with Python  
Practice 1: Interactive Personal Budget Manager

A small command-line budget manager. You can add income and expenses,
list them, print a report, import a CSV file, save and load JSON, and
undo the last transaction. Invalid data is rejected with a clear message
and is never silently "fixed".

## Setup

The program uses only the Python standard library. You need Python 3.10
or newer (it was developed with Python 3.13). If the `python` command is
not found, use `python3` instead.

```bash
cd Practice_I_Teun_Schulten
```

No packages need to be installed to run the program or the tests.

Commands below assume you are in this project folder and that Python can
import the package from `src`:

```bash
export PYTHONPATH=src
```

On Windows (cmd): `set PYTHONPATH=src`.

## Run

```bash
python -m budget_manager --help
```

The default data file is `transactions.json` in the current folder. It
is created automatically on the first change. Use `--file path.json` to
choose a different file. Every `add`, `import`, `undo`, and `load`
command writes the file immediately (atomic replace, so a crash cannot
leave a half-written file as the only copy).

## Examples

Add two transactions and inspect them:

```bash
python -m budget_manager add --date 2026-09-04 --kind expense --category food --amount 18.50 --currency EUR
python -m budget_manager add --date 2026-09-05 --kind income --category salary --amount 2500 --currency EUR
python -m budget_manager list
python -m budget_manager report
```

Expected list (aligned columns):

```
T001  2026-09-04  expense  food               18.50 EUR
T002  2026-09-05  income   salary           2500.00 EUR
```

Expected report:

```
Transactions: 2

Currency: EUR
  Income:  2500.00
  Expense: 18.50
  Balance: 2481.50
  By category:
    salary          +2500.00
    food            -18.50
```

Import the sample CSV (valid rows are stored; invalid rows are reported):

```bash
python -m budget_manager --file demo.json import data/sample_transactions.csv
```

Expected output (errors go to stderr, but appear together in a terminal).
The command exits with status 1 when any row is rejected; the five valid
rows are still saved:

```
Imported 5 transaction(s).
Row 4: amount must be > 0.
Row 5: category must be one of: education, entertainment, food, freelance, gift, health, rent, salary, shopping, transport, utilities.
Row 6: date must be a real calendar date in ISO format YYYY-MM-DD.
Row 7: kind must be 'expense' or 'income'.
Row 8: amount must be > 0.
Row 9: currency must be a 3-letter ISO code (e.g. EUR).
```

Save a copy, load it back, and undo the last stored transaction:

```bash
python -m budget_manager --file demo.json save backup.json
python -m budget_manager --file demo.json load backup.json
python -m budget_manager --file demo.json undo
python -m budget_manager --file demo.json list
```

`save` will not overwrite an existing backup, so you cannot accidentally
destroy your only recovery copy. If `backup.json` already exists, the
command prints an error and exits with status 1. Choose a new filename,
or pass `--force` to replace the file on purpose:

```bash
python -m budget_manager --file demo.json save backup.json --force
```

The live data file (`transactions.json`, or the path given with `--file`)
is still updated in place after `add`, `import`, `undo`, and `load`.

Optional filters:

```bash
python -m budget_manager list --kind expense
python -m budget_manager list --category food
```

## Interactive mode

To add more than one transaction without restarting, start the menu loop:

```bash
python -m budget_manager interactive
```

Use `--file` as usual if you want a different JSON file. The menu repeats
until you type `q`. Every add and undo is saved immediately. Invalid
input is shown as a clear error and is not stored; you then return to
the menu.

Example session:

```
$ python -m budget_manager interactive
1) Add transaction
2) List transactions
3) Report
4) Undo last
q) Quit
Choose an option: 1
Date (YYYY-MM-DD): 2026-09-04
Kind (expense or income): expense
Category (education, entertainment, food, freelance, gift, health, rent, salary, shopping, transport, utilities): food
Amount: 18.50
Currency (e.g. EUR): EUR
Added T001.
1) Add transaction
2) List transactions
3) Report
4) Undo last
q) Quit
Choose an option: 1
Date (YYYY-MM-DD): 2026-09-06
Kind (expense or income): expense
Category (education, entertainment, food, freelance, gift, health, rent, salary, shopping, transport, utilities): food
Amount: -5
Currency (e.g. EUR): EUR
Error: amount must be > 0.
1) Add transaction
2) List transactions
3) Report
4) Undo last
q) Quit
Choose an option: 3
Transactions: 1

Currency: EUR
  Income:  0.00
  Expense: 18.50
  Balance: -18.50
  By category:
    food            -18.50
1) Add transaction
2) List transactions
3) Report
4) Undo last
q) Quit
Choose an option: q
Goodbye.
```

## How to test

From this project folder (PYTHONPATH is not required for the test
command, because the tests add `src` to the path themselves):

```bash
python -m unittest discover -s tests -v
```

There is a normal-case test (add + report totals) and several boundary
tests: negative and zero amounts, an unknown category, a lowercase
currency code, an impossible date, CSV row-error messages, mixed
currencies, undo after a simulated crash and reload, a refused overwrite of an existing backup, and the interactive menu (a valid add, a rejected negative amount, and an unknown option).

You can also open `Practice_I_Teun_Schulten.ipynb` (and the HTML
export) for a recorded walk-through of expected behaviour, CLI runs,
and test output.

## Transaction schema

Every record has all of these fields:

| Field    | Rule |
|----------|------|
| `id`     | Unique, `T` plus at least three digits (`T001`) |
| `date`   | Real calendar date in ISO format `YYYY-MM-DD` |
| `kind`   | `expense` or `income` |
| `category` | One value from the controlled vocabulary below |
| `amount` | A number strictly greater than 0 |
| `currency` | 3-letter uppercase ISO-style code (`EUR`) |

Allowed categories: `education`, `entertainment`, `food`, `freelance`,
`gift`, `health`, `rent`, `salary`, `shopping`, `transport`, `utilities`.

Policy for unknown categories: they are **rejected**, with a message
that lists the allowed values. They are not mapped to a generic bucket.

## Project layout

```
Practice_I_Teun_Schulten/
├── README.md
├── DESIGN.md
├── AI_DISCLOSURE.md
├── .gitignore
├── Practice_I_Teun_Schulten.ipynb
├── Practice_I_Teun_Schulten.html
├── data/sample_transactions.csv
├── src/budget_manager/
│   ├── models.py        # Transaction schema
│   ├── validation.py    # boundary checks, clear error messages
│   ├── services.py      # add, list, summarize, import, undo
│   ├── storage.py       # load/save JSON (atomic write)
│   └── cli.py           # command-line interaction only
└── tests/test_budget_manager.py
```

## Known limitations

- There is no graphical interface and no login or multi-user support.
- Amounts use Python `float`, as required by the schema. This is fine
  for a course project, but not ideal for real money at large scale.
- Currency codes are checked for shape (`EUR`, not `eur` or `EU`) but
  not against the official ISO 4217 table, so a made-up code such as
  `XXX` is accepted.
- Mixed currencies are reported separately. The program never converts
  between currencies.
- `list` can filter by kind or category, but there is no date-range
  filter and no monthly budget cap in Release 1.
- Undo removes only the last transaction in the stored list. There is
  no redo, and no undo of a specific older id.
- The default file is wherever you run the command from
  (`transactions.json`). It is not stored in a hidden user folder.
