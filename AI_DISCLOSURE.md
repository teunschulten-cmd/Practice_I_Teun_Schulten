# AI disclosure

This project was made with the help of an AI assistant: Claude (Anthropic).

## How I used it

I used Claude for every part of the project as a step-by-step guide.
For each part, Claude explained what was needed and why, and gave
example code. I then worked through it myself in my own project: typing
and adjusting the code, running it, and fixing errors until it worked.

This covered all parts of the release:

- the package layout (`models.py`, `validation.py`, `services.py`,
  `storage.py`, `cli.py`)
- the transaction model and the validation rules with clear error messages
- the service functions: add, list, report, CSV import and undo
- saving and loading JSON with a safe (atomic) write, and refusing to
  overwrite an existing backup
- the argparse command-line interface
- the interactive menu mode (`interactive` command) and its test
- the sample CSV with valid and invalid rows
- the unit tests
- the documentation (README, DESIGN, this file) and the practice notebook

I worked with Claude on different laptops, so I no longer have the full
conversations.

## Why I used it

I am new to programming in Python. I used Claude as a tutor to understand
each step of the Practice 1 brief (transaction schema, separate layers,
validation at the boundaries, delivery evidence and the undo stretch
goal), so that I could build the release myself and explain how it works.

## What I checked myself

I ran the unit tests, the interactive menu and the command-line examples
from the README and checked that the results matched the expected output.
I remain responsible for the work I hand in.
