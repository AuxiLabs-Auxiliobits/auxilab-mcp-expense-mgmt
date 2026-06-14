"""Baseline ruleset — the deterministic, structured-JSON policy tier (SCOPING §4, §20.B).

Owned by Admin, checked at intake (Line 1). Agency-specific *document* policy (the RAG
tier interpreted by the LLM approver) is a separate concern handled in the workers package.
"""

from __future__ import annotations

import json
from decimal import Decimal
from enum import StrEnum
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from expense_core.schemas.enums import Category


class CapBoundary(StrEnum):
    INCLUSIVE = "inclusive"  # amount == cap passes; only above fails (SCOPING §19.3)
    EXCLUSIVE = "exclusive"


class BaselinePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    per_meal_limit: Decimal
    per_hotel_night_limit: Decimal
    prohibited_categories: list[Category] = Field(default_factory=list)
    receipt_required_threshold: Decimal
    submission_cutoff: str = "month_end_of_incurred_month"
    max_file_mb: int = 25
    allowed_extensions: list[str] = Field(default_factory=list)
    duplicate_near_match_days: int = 3
    cap_boundary: CapBoundary = CapBoundary.INCLUSIVE
    llm_confidence_routing_threshold: float = 0.7
    currency: str = "USD"

    def exceeds_cap(self, amount: Decimal, cap: Decimal) -> bool:
        """Single source of truth for the inclusive/exclusive cap boundary."""
        return amount > cap if self.cap_boundary is CapBoundary.INCLUSIVE else amount >= cap


def load_baseline_policy(path: str | Path | None = None) -> BaselinePolicy:
    """Load the baseline policy. Defaults to the packaged JSON; pass a path to override
    (e.g. an Admin-edited ruleset persisted in the DB and written to a temp file)."""
    if path is None:
        text = resources.files("expense_core.policy").joinpath("baseline_policy.json").read_text()
    else:
        text = Path(path).read_text()
    return BaselinePolicy.model_validate(json.loads(text))
