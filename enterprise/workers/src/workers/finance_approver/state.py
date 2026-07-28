"""LangGraph run state for the LLM Finance Approver (SCOPING §6.3, §9.2).

Pydantic models for the sheet under review, the agency policy retrieved for it, each
per-item verdict (with its cited clause), and the audit-ready sheet-level result. Reuses
the canonical enums from `expense_core` (FinanceDecision, LineItemStatus) so the worker,
API, and DB speak the same vocabulary.
"""

from __future__ import annotations

from decimal import Decimal

from expense_core.schemas.enums import FinanceDecision, LineItemStatus
from pydantic import BaseModel, Field


class ApproverLineItem(BaseModel):
    """One expense line the approver judges against the agency policy (SCOPING §5)."""

    id: str
    category: str | None = None
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = "USD"
    merchant: str = ""
    description: str = ""


class LineItemVerdict(BaseModel):
    """Per-item finance verdict with mandatory citation (SCOPING §6.3, §9.2).

    `status` is POLICY_PASS / POLICY_FAIL / POLICY_UNCERTAIN. A passing or failing verdict
    must cite the governing clause; an uncitable / low-confidence / numerically-disputed
    judgement becomes POLICY_UNCERTAIN → the sheet routes to a human.
    """

    line_item_id: str
    status: LineItemStatus
    cited_clause: str | None = None  # the policy clause the verdict rests on
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    numeric_cross_checked: bool = False  # a deterministic cap check was applied


class SheetResult(BaseModel):
    """Audit-ready sheet-level decision (SCOPING §6.3, §6.4, §9.2).

    All-or-nothing: any failing item rejects the whole sheet; any uncertain/missing-policy
    item routes the whole sheet to a human. Pins model + policy version for replay.
    """

    sheet_id: str
    agency_id: str
    decision: FinanceDecision
    line_item_verdicts: list[LineItemVerdict] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    model_version: str = "unknown"
    policy_version: str = "unknown"
    tokens_used: int = 0
    comments: list[str] = Field(default_factory=list)  # cited reasons for reject/route


class FinanceApproverState(BaseModel):
    """The LangGraph channel state threaded through the approver nodes (SCOPING §6.3).

    Inputs are the sheet + agency; nodes progressively fill in the retrieved policy, the
    per-item verdicts, and finally the sheet-level decision. `confidence_threshold` and
    `token_budget` carry the guardrail config (SCOPING §9.2, §8).
    """

    # --- Inputs ---
    sheet_id: str
    agency_id: str
    line_items: list[ApproverLineItem] = Field(default_factory=list)

    # --- Guardrail config (SCOPING §6.4, §9.2) ---
    confidence_threshold: float = 0.7
    token_budget: int = 20_000

    # --- Filled by retrieve_policy ---
    policy_clauses: list[str] = Field(default_factory=list)
    policy_version: str = "unknown"
    policy_missing: bool = False  # empty/garbled policy → route (SCOPING §8)

    # --- Filled by iterate_line_items ---
    verdicts: list[LineItemVerdict] = Field(default_factory=list)

    # --- Filled by aggregate ---
    decision: FinanceDecision | None = None
    sheet_confidence: float = 1.0
    model_version: str = "unknown"
    tokens_used: int = 0
    routed_to_human: bool = False  # interrupt flag for checkpoint resume (SCOPING §11)

    def to_result(self) -> SheetResult:
        """Project the terminal state into the audit-ready sheet result."""
        comments = [
            f"[{v.line_item_id}] {v.reason}"
            for v in self.verdicts
            if v.status in (LineItemStatus.POLICY_FAIL, LineItemStatus.POLICY_UNCERTAIN)
        ]
        return SheetResult(
            sheet_id=self.sheet_id,
            agency_id=self.agency_id,
            decision=self.decision or FinanceDecision.ROUTED_TO_HUMAN,
            line_item_verdicts=self.verdicts,
            confidence=self.sheet_confidence,
            model_version=self.model_version,
            policy_version=self.policy_version,
            tokens_used=self.tokens_used,
            comments=comments,
        )
