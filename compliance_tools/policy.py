"""The policy ruleset the Policy Checker evaluates against.

A policy is plain JSON — no code, no DSL — so teams can version it in git, diff it in a
pull request, and hand it to the checker without redeploying anything::

    from compliance_tools import load_policy, check_policy
    policy = load_policy("my-company-policy.json")

``load_policy()`` with no argument returns the packaged default in
``compliance_tools/baseline_policy.json``.
"""

from __future__ import annotations

import json
from decimal import Decimal
from enum import StrEnum
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from compliance_tools.schemas import Category


class CapBoundary(StrEnum):
    """Whether an amount exactly equal to the cap is allowed."""

    INCLUSIVE = "inclusive"  # amount == cap passes; only strictly above fails
    EXCLUSIVE = "exclusive"  # amount == cap fails


class BaselinePolicy(BaseModel):
    """A complete, self-contained expense policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: str = "USD"

    #: Categories that are never reimbursable, whatever the amount.
    prohibited_categories: list[Category] = Field(default_factory=list)

    #: Per-category spend caps. Categories absent from this map are uncapped.
    category_limits: dict[Category, Decimal] = Field(default_factory=dict)

    #: A receipt is mandatory once an expense exceeds this amount. ``None`` disables.
    receipt_required_over: Decimal | None = Decimal("25")

    #: Expenses older than this many days are outside the claim window. ``None`` disables.
    max_expense_age_days: int | None = 90

    #: Window used by the duplicate detector when comparing near-matching receipts.
    duplicate_near_match_days: int = 3

    #: How to treat an amount exactly equal to a cap.
    cap_boundary: CapBoundary = CapBoundary.INCLUSIVE

    def exceeds_cap(self, amount: Decimal, cap: Decimal) -> bool:
        """Single source of truth for the inclusive/exclusive cap boundary."""
        return amount > cap if self.cap_boundary is CapBoundary.INCLUSIVE else amount >= cap

    def limit_for(self, category: Category | None) -> Decimal | None:
        """The cap for ``category``, or ``None`` when it is uncapped."""
        if category is None:
            return None
        return self.category_limits.get(category)


def load_policy(path: str | Path | None = None) -> BaselinePolicy:
    """Load a policy from JSON. Defaults to the packaged baseline."""
    if path is None:
        text = (
            resources.files("compliance_tools").joinpath("baseline_policy.json").read_text("utf-8")
        )
    else:
        text = Path(path).read_text("utf-8")
    return BaselinePolicy.model_validate(json.loads(text))
