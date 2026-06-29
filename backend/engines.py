"""
ExpenseOps Core Validation Engines
====================================
Three engines that form the heart of the expense validation pipeline:

1. **PolicyEngine** – checks an expense against policy rules (amount caps,
   receipt requirements, role-based access).
2. **RiskEngine** – computes a composite 0–100 risk score from four weighted
   factors (amount variance, timing anomaly, category baseline, duplicate
   probability).
3. **DuplicateEngine** – detects duplicate submissions using amount + date
   proximity + Levenshtein merchant-name matching.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

from Levenshtein import distance as levenshtein_distance
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from backend.database import (
    ClaimError,
    DuplicateHistory,
    ExpenseClaim,
    PolicyRule,
)
from backend.schemas import (
    DuplicateCheckResult,
    PolicyCheckResult,
    RiskScoreResult,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Base Types & Engine Interface
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ExpenseContext:
    """
    Standardized context object holding parsed expense data.
    Passed universally into engine evaluation methods to prevent repetitive parsing.
    """
    amount: float
    category: str
    merchant_name: str
    transaction_date: date
    employee_id: str
    employee_role: str
    receipt_path: Optional[str] = None
    location: Optional[str] = None
    submission_hour: int = 12

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExpenseContext":
        return cls(
            amount=float(data.get("amount", 0)),
            category=data.get("category", ""),
            merchant_name=data.get("merchant_name", ""),
            transaction_date=data.get("transaction_date", date.today()),
            employee_id=data.get("employee_id", ""),
            employee_role=data.get("employee_role", ""),
            receipt_path=data.get("receipt_path"),
            location=data.get("location"),
            submission_hour=int(data.get("submission_hour", 12))
        )


class BaseEngine(ABC):
    """
    Abstract base class for all validation and routing engines.
    Engines are initialized once per evaluation pipeline.
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    @abstractmethod
    def evaluate(self, context: ExpenseContext, **kwargs) -> Any:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Policy Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PolicyEngine(BaseEngine):
    """
    Evaluates an expense claim against the company's policy rules stored in
    the ``policy_rules`` table.

    Algorithm:
        1. Fetch all rules whose ``category`` matches the expense.
        2. Filter to rules whose ``allowed_roles`` list includes the
           employee's role.
        3. Sort by ``precedence`` DESC and select the highest-precedence rule.
        4. Check amount vs. ``max_amount``.
        5. Check receipt requirement (if amount > $50 and no receipt).
        6. Check location restrictions (if any).
        7. Return PASS or EXCEPTION with a list of failed rule IDs.
    """

    def evaluate(self, context: ExpenseContext, **kwargs) -> PolicyCheckResult:
        """
        Evaluates the ExpenseContext against policy rules.

        Returns
        -------
        PolicyCheckResult
        """
        failed_rules: list[str] = []
        risk_contribution: float = 0.0

        # ── Step 1: Fetch rules for this category ──────────────────────
        rules = (
            self.db.query(PolicyRule)
            .filter(PolicyRule.category == context.category)
            .all()
        )

        if not rules:
            # No policy rule found for this category – pass by default
            # but flag for manual review since the category is uncovered.
            return PolicyCheckResult(
                status="PASS",
                failed_rules=[],
                risk_score=10.0,
                requires_manual_review=True,
                recommended_action="hold_for_review",
            )

        # ── Step 2: Filter by employee role ────────────────────────────
        matching_rules: list[PolicyRule] = []
        for rule in rules:
            try:
                allowed = json.loads(rule.allowed_roles) if isinstance(rule.allowed_roles, str) else (rule.allowed_roles or [])
            except (json.JSONDecodeError, TypeError):
                allowed = []

            if not allowed or context.employee_role in allowed:
                matching_rules.append(rule)

        if not matching_rules:
            # Employee's role is not authorised for this category at all
            failed_rules.append(f"ROLE_UNAUTHORIZED:{context.category}")
            return PolicyCheckResult(
                status="EXCEPTION",
                failed_rules=failed_rules,
                risk_score=50.0,
                requires_manual_review=True,
                recommended_action="reject",
            )

        # ── Step 3: Pick the highest-precedence rule ───────────────────
        matching_rules.sort(key=lambda r: r.precedence, reverse=True)
        best_rule: PolicyRule = matching_rules[0]

        # ── Step 4: Amount check ───────────────────────────────────────
        if context.amount > best_rule.max_amount:
            overage_pct = ((context.amount - best_rule.max_amount) / best_rule.max_amount) * 100
            failed_rules.append(
                f"{best_rule.rule_id}: amount ${context.amount:.2f} exceeds cap ${best_rule.max_amount:.2f}"
            )
            # Risk contribution scales with how far over the cap we are
            risk_contribution += min(50.0, overage_pct * 0.5)

        # ── Step 5: Receipt requirement ────────────────────────────────
        # Global rule: receipts required above $50
        receipt_required = best_rule.requires_receipt or context.amount > 50.0
        if receipt_required and not context.receipt_path:
            failed_rules.append(
                f"{best_rule.rule_id}: receipt required for ${context.amount:.2f}"
            )
            risk_contribution += 10.0

        # ── Step 6: Location restrictions ──────────────────────────────
        if context.location:
            try:
                loc_restrictions = (
                    json.loads(best_rule.location_restrictions)
                    if isinstance(best_rule.location_restrictions, str)
                    else (best_rule.location_restrictions or [])
                )
            except (json.JSONDecodeError, TypeError):
                loc_restrictions = []

            if loc_restrictions and context.location not in loc_restrictions:
                failed_rules.append(
                    f"{best_rule.rule_id}: location '{context.location}' not in allowed list"
                )
                risk_contribution += 15.0

        # ── Build result ───────────────────────────────────────────────
        if failed_rules:
            return PolicyCheckResult(
                status="EXCEPTION",
                failed_rules=failed_rules,
                risk_score=risk_contribution,
                requires_manual_review=True,
                recommended_action="hold_for_review" if risk_contribution < 40 else "reject",
            )

        return PolicyCheckResult(
            status="PASS",
            failed_rules=[],
            risk_score=0.0,
            requires_manual_review=False,
            recommended_action="auto_approve",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Risk Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Category-level average amounts used as baselines for variance scoring.
# These would typically be computed from historical data; hardcoded here
# for deterministic behaviour in the demo.
_CATEGORY_AVERAGES: dict[str, float] = {
    "Meals": 50.0,
    "Travel-Air": 800.0,
    "Travel-Hotel": 200.0,
    "Travel-Ground": 40.0,
    "Entertainment": 120.0,
    "Office Supplies": 80.0,
    "Software": 250.0,
}

# Category-specific risk baselines (higher = inherently riskier category)
_CATEGORY_RISK_BASELINES: dict[str, float] = {
    "Entertainment": 70.0,
    "Travel-Air": 40.0,
    "Meals": 30.0,
    "Travel-Hotel": 35.0,
    "Travel-Ground": 25.0,
    "Office Supplies": 15.0,
    "Software": 20.0,
}


class RiskEngine(BaseEngine):
    """
    Computes a composite risk score on a 0–100 scale from four weighted
    factors:

        R = S_amount × 0.35 + S_time × 0.15 + S_category × 0.20 + P_dup × 0.30

    Each sub-score is capped at 100 before weighting.
    """

    def evaluate(
        self,
        context: ExpenseContext,
        policy_result: PolicyCheckResult = None,
        duplicate_result: DuplicateCheckResult = None,
        **kwargs
    ) -> RiskScoreResult:
        """
        Parameters
        ----------
        context : ExpenseContext
        policy_result : PolicyCheckResult
            Output from PolicyEngine (used to add policy-failure risk).
        duplicate_result : DuplicateCheckResult
            Output from DuplicateEngine.

        Returns
        -------
        RiskScoreResult
        """
        if not policy_result or not duplicate_result:
            raise ValueError("RiskEngine requires policy_result and duplicate_result.")
            
        factors: dict[str, Any] = {}

        # ── S_amount: % variance over category average × 0.35 ─────────
        avg = _CATEGORY_AVERAGES.get(context.category, 100.0)
        if context.amount > avg:
            variance_pct = ((context.amount - avg) / avg) * 100
            s_amount = min(100.0, variance_pct)
        else:
            s_amount = 0.0
        factors["amount_variance"] = {
            "raw_score": round(s_amount, 2),
            "weight": 0.35,
            "weighted": round(s_amount * 0.35, 2),
            "detail": f"${context.amount:.2f} vs avg ${avg:.2f}",
        }

        # ── S_time: off-hours / weekend check × 0.15 ──────────────────
        is_weekend = context.transaction_date.weekday() >= 5  # Saturday=5, Sunday=6
        is_off_hours = context.submission_hour < 6 or context.submission_hour >= 22

        if is_weekend:
            s_time = 80.0
        elif is_off_hours:
            s_time = 60.0
        else:
            s_time = 0.0
        factors["timing_anomaly"] = {
            "raw_score": round(s_time, 2),
            "weight": 0.15,
            "weighted": round(s_time * 0.15, 2),
            "detail": f"weekend={is_weekend}, off_hours={is_off_hours}",
        }

        # ── S_category: category risk baseline × 0.20 ─────────────────
        s_category = _CATEGORY_RISK_BASELINES.get(context.category, 20.0)
        factors["category_risk"] = {
            "raw_score": round(s_category, 2),
            "weight": 0.20,
            "weighted": round(s_category * 0.20, 2),
            "detail": f"baseline for '{context.category}'",
        }

        # ── P_duplicate: duplicate probability × 0.30 ─────────────────
        if duplicate_result.is_duplicate:
            p_dup = duplicate_result.similarity_score * 100.0
        else:
            p_dup = 0.0
        factors["duplicate_probability"] = {
            "raw_score": round(p_dup, 2),
            "weight": 0.30,
            "weighted": round(p_dup * 0.30, 2),
            "detail": f"dup={duplicate_result.is_duplicate}, score={duplicate_result.similarity_score}",
        }

        # ── Composite score ────────────────────────────────────────────
        raw_score = (
            s_amount * 0.35
            + s_time * 0.15
            + s_category * 0.20
            + p_dup * 0.30
        )
        # Add policy-failure contribution (if any)
        raw_score += policy_result.risk_score * 0.10
        score = min(100.0, round(raw_score, 2))

        # ── Risk level bucketing ───────────────────────────────────────
        if score < 35:
            level = "LOW"
            action = "auto_approve"
        elif score < 70:
            level = "MEDIUM"
            action = "flag_for_review"
        else:
            level = "HIGH"
            action = "escalate"

        return RiskScoreResult(
            score=score,
            level=level,
            factors=factors,
            recommended_action=action,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Duplicate Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DuplicateEngine(BaseEngine):
    """
    Detects duplicate expense submissions by comparing amount, date proximity,
    and merchant-name similarity (Levenshtein distance ≤ 2).

    Detection algorithm:
        1. Query existing claims with the **exact same amount** and a
           ``transaction_date`` within ±2 days.
        2. For each candidate, compute Levenshtein distance on
           ``merchant_name``.  If distance ≤ 2 → potential duplicate.
        3. Also flag if the same employee submitted both.
        4. Record matches in the ``duplicate_history`` table.
    """

    def evaluate(
        self,
        context: ExpenseContext,
        exclude_claim_id: Optional[str] = None,
        **kwargs
    ) -> DuplicateCheckResult:
        """
        Parameters
        ----------
        context : ExpenseContext
        exclude_claim_id : str, optional
            Claim ID to exclude from duplicate search (e.g. the claim itself).

        Returns
        -------
        DuplicateCheckResult
        """

        # ── Step 1: Query candidates with same amount ± 2 days ─────────
        date_low = context.transaction_date - timedelta(days=2)
        date_high = context.transaction_date + timedelta(days=2)

        query = self.db.query(ExpenseClaim).filter(
            and_(
                ExpenseClaim.transaction_date >= date_low,
                ExpenseClaim.transaction_date <= date_high,
            )
        )

        # Exclude the claim we're checking (if it already exists in DB)
        if exclude_claim_id:
            query = query.filter(ExpenseClaim.claim_id != exclude_claim_id)

        candidates = query.all()

        matched_claim_ids: list[str] = []
        best_similarity: float = 0.0

        for candidate in candidates:
            # ── Step 2: Levenshtein distance on merchant name ──────────
            dist = levenshtein_distance(
                context.merchant_name.lower().strip(),
                candidate.merchant_name.lower().strip(),
            )

            # Threshold: distance ≤ 2 means the names are very close
            if dist <= 2:
                # We consider it a duplicate if either the amount is identical
                # OR it's the exact same date and same employee (catching OCR amount errors)
                is_same_amount = (context.amount == float(candidate.amount))
                is_same_day_employee = (candidate.transaction_date == context.transaction_date and candidate.employee_id == context.employee_id)

                if is_same_amount or is_same_day_employee:
                    # Compute similarity score (1.0 = perfect match)
                    max_len = max(len(context.merchant_name), len(candidate.merchant_name), 1)
                    similarity = 1.0 - (dist / max_len)

                    # ── Step 3: Boost if same employee ─────────────────────
                    if candidate.employee_id == context.employee_id:
                        similarity = min(1.0, similarity + 0.1)

                    if similarity > best_similarity:
                        best_similarity = similarity

                    matched_claim_ids.append(candidate.claim_id)

                    # ── Step 4: Record in duplicate_history ────────────────
                    try:
                        dup_record = DuplicateHistory(
                            original_claim_id=candidate.claim_id,
                            duplicate_claim_id=exclude_claim_id or "NEW",
                            merchant=context.merchant_name,
                            amount=context.amount,
                            employee=context.employee_id,
                            date=context.transaction_date,
                            similarity_score=round(similarity, 4),
                        )
                        self.db.add(dup_record)
                        self.db.flush()
                    except Exception as exc:
                        logger.warning("Failed to record duplicate history: %s", exc)

        is_dup = len(matched_claim_ids) > 0

        return DuplicateCheckResult(
            is_duplicate=is_dup,
            matched_claims=matched_claim_ids,
            similarity_score=round(best_similarity, 4),
        )
