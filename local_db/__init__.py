"""Local SQLite persistence for the expense tools.

>>> from local_db import get_store
>>> store = get_store()          # creates + seeds local_db/sqlite.db on first call
>>> store.stats()["line_items"]  # doctest: +SKIP
6
"""

from __future__ import annotations

from local_db.store import DEFAULT_DB_PATH, ExpenseStore, get_store

__all__ = ["DEFAULT_DB_PATH", "ExpenseStore", "get_store"]
