"""Allow `python -m budget_manager` to start the command-line interface."""

import sys

from budget_manager.cli import main

if __name__ == "__main__":
    sys.exit(main())
