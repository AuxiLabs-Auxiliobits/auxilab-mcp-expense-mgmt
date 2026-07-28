"""Shared fixtures.

Every test runs against an isolated temporary database, so the suite never touches
``local_db/sqlite.db`` and tests can't leak state into one another.
"""

from __future__ import annotations

from datetime import date

import pytest

import local_db.store as store_module
from compliance_tools import BaselinePolicy, load_policy
from compliance_tools.schemas import Category
from local_db import ExpenseStore

#: Fixed "today" so date-sensitive rules are deterministic.
TODAY = date(2026, 6, 15)


@pytest.fixture
def store(tmp_path):
    """An empty store backed by a throwaway file."""
    with ExpenseStore(tmp_path / "test.db") as s:
        yield s


@pytest.fixture
def shared_store(monkeypatch, tmp_path):
    """Redirect the process-wide store to a throwaway, seeded database.

    Both the env var and the cached singleton are set: entry points resolve the store
    through ``EXPENSE_DB_PATH`` on every call, and ``get_store`` reopens if it is asked
    for a path other than the one it is holding.
    """
    db_path = tmp_path / "shared.db"
    monkeypatch.setenv("EXPENSE_DB_PATH", str(db_path))
    monkeypatch.setattr(store_module, "_default_store", None)

    created = store_module.get_store()  # created and seeded on first call
    yield created
    created.close()


@pytest.fixture
def seeded_store(store):
    """A store preloaded with the demo dataset."""
    store.seed()
    return store


@pytest.fixture
def policy() -> BaselinePolicy:
    """The packaged baseline policy."""
    return load_policy()


@pytest.fixture
def strict_policy() -> BaselinePolicy:
    """A policy with every optional rule switched on, for exercising edge cases."""
    return BaselinePolicy(
        currency="USD",
        prohibited_categories=[Category.CLIENT_ENTERTAINMENT],
        category_limits={Category.MEALS_ENTERTAINMENT: 75},
        receipt_required_over=25,
        max_expense_age_days=90,
        duplicate_near_match_days=3,
    )
