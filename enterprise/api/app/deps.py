"""Shared FastAPI dependencies not tied to auth."""

from __future__ import annotations

from functools import lru_cache

from expense_core.policy import BaselinePolicy, load_baseline_policy


@lru_cache(maxsize=1)
def get_policy() -> BaselinePolicy:
    """The Admin-owned baseline ruleset (SCOPING §20.B). Cached; in a full build this is
    loaded from the DB-backed Admin config rather than the packaged default."""
    return load_baseline_policy()
