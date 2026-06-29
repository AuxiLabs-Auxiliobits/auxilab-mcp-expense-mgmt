"""Entrypoint so the eval is runnable as ``python -m expense_core.evals``."""

from __future__ import annotations

import sys

from expense_core.evals.runner import run

if __name__ == "__main__":
    sys.exit(run())
