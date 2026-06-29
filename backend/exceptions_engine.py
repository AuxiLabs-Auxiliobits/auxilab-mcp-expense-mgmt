"""
ExpenseOps Exception Engine
=============================
Handles policy exceptions through a tiered escalation model:

  • **Tier 1** – Amount-based overages → route to direct manager.
  • **Tier 2** – High-risk / fraud indicators → route to central auditor.
  • **VIP Override** – C-Suite roles get elevated limits and auto-approval.
  • **Location Override** – Cost-of-living adjustments from exceptions.json.

Conflict resolution: when a VIP override *and* a restriction both apply,
the **most restrictive rule wins** (safety-first design).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.schemas import PolicyCheckResult, RiskScoreResult
from backend.engines import BaseEngine, ExpenseContext

logger = logging.getLogger(__name__)


def _load_exceptions_file() -> dict[str, Any]:
    """
    Load the exceptions JSON file.  Returns an empty dict on any error
    so the engine degrades gracefully.
    """
    settings = get_settings()
    path = settings.EXCEPTIONS_FILE_PATH

    if not os.path.isfile(path):
        logger.warning("Exceptions file not found at %s", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load exceptions file: %s", exc)
        return {}


class ExceptionEngine(BaseEngine):
    """
    Determines how to handle a policy exception (i.e. a claim that failed
    one or more policy rules).

    Returns a dict with:
        - tier (int): 1 or 2
        - action (str): "route_to_manager" | "route_to_auditor" | "auto_approve" | "reject"
        - escalation_path (str): human-readable routing description
        - override_applied (str | None): which override was used, if any
        - adjusted_max (float | None): new cap after override, if applicable
    """

    def evaluate(
        self,
        context: ExpenseContext,
        policy_result: PolicyCheckResult = None,
        risk_result: RiskScoreResult = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Evaluate the exception and decide routing / override.

        Parameters
        ----------
        context : ExpenseContext
        policy_result : PolicyCheckResult
        risk_result : RiskScoreResult

        Returns
        -------
        dict with keys: tier, action, escalation_path, override_applied, adjusted_max
        """
        if not policy_result or not risk_result:
            raise ValueError("ExceptionEngine requires policy_result and risk_result.")

        exceptions_data = _load_exceptions_file()
        vip_overrides = exceptions_data.get("vip_overrides", {})
        location_overrides = exceptions_data.get("location_overrides", {})

        result: dict[str, Any] = {
            "tier": 1,
            "action": "route_to_manager",
            "escalation_path": "Direct manager review required.",
            "override_applied": None,
            "adjusted_max": None,
        }

        # ── Tier 2 check: High-risk / fraud ────────────────────────────
        # If the risk engine flagged this as HIGH (score >= 70), escalate
        # straight to central audit — bypasses normal manager approval.
        if risk_result.level == "HIGH":
            result["tier"] = 2
            result["action"] = "route_to_auditor"
            result["escalation_path"] = (
                f"Central audit review required – risk score {risk_result.score:.1f} "
                f"(level: {risk_result.level})."
            )
            # Even VIP overrides do NOT bypass Tier-2 fraud escalation
            # (most-restrictive-rule principle).
            return result

        # ── VIP Override check ─────────────────────────────────────────
        vip_config = vip_overrides.get(context.employee_role)
        if vip_config:
            multiplier: float = vip_config.get("max_multiplier", 1.0)
            auto_approve: bool = vip_config.get("auto_approve", False)

            # Compute the adjusted max for this category.
            # We need the original cap — extract from policy_result failed_rules
            original_cap = _extract_cap_from_failed_rules(policy_result.failed_rules)
            if original_cap is not None:
                adjusted_max = original_cap * multiplier

                if context.amount <= adjusted_max and auto_approve:
                    # VIP override grants auto-approval
                    result["tier"] = 0  # no escalation needed
                    result["action"] = "auto_approve"
                    result["escalation_path"] = (
                        f"VIP override ({context.employee_role}): auto-approved up to "
                        f"${adjusted_max:.2f} ({multiplier}x cap)."
                    )
                    result["override_applied"] = f"VIP_{context.employee_role}"
                    result["adjusted_max"] = adjusted_max
                    return result
                elif context.amount <= adjusted_max and not auto_approve:
                    # Within elevated cap but still needs approval
                    result["tier"] = 1
                    result["action"] = "route_to_manager"
                    result["escalation_path"] = (
                        f"VIP elevated cap ({context.employee_role}): ${adjusted_max:.2f}. "
                        f"Manager approval required."
                    )
                    result["override_applied"] = f"VIP_{context.employee_role}"
                    result["adjusted_max"] = adjusted_max
                    return result
                # If amount > adjusted_max, fall through to location check
                # and then normal escalation.

        # ── Location Override check ────────────────────────────────────
        if context.location and context.location in location_overrides:
            loc_config = location_overrides[context.location]
            if context.category in loc_config:
                loc_max = loc_config[context.category].get("max_amount_override")
                if loc_max is not None and context.amount <= loc_max:
                    result["tier"] = 1
                    result["action"] = "route_to_manager"
                    result["escalation_path"] = (
                        f"Location override ({context.location}): cap raised to "
                        f"${loc_max:.2f} for {context.category}. Manager review needed."
                    )
                    result["override_applied"] = f"LOCATION_{context.location}"
                    result["adjusted_max"] = loc_max
                    return result

        # ── Conflict resolution: most restrictive rule ─────────────────
        # If we have both a VIP override *and* a location restriction and
        # neither passed, we keep the Tier-1 escalation (most restrictive).

        # ── Default Tier-1 escalation ──────────────────────────────────
        result["escalation_path"] = (
            f"Amount ${context.amount:.2f} in {context.category} exceeds policy cap. "
            f"Routed to direct manager for review."
        )
        return result


def _extract_cap_from_failed_rules(failed_rules: list[str]) -> Optional[float]:
    """
    Parse the original cap amount from failed-rule strings like:
        "RULE_MEAL_ENG: amount $95.00 exceeds cap $75.00"
    Returns the cap value or None if it can't be parsed.
    """
    import re
    for rule_str in failed_rules:
        match = re.search(r"exceeds cap \$([0-9]+(?:\.[0-9]+)?)", rule_str)
        if match:
            return float(match.group(1))
    return None
