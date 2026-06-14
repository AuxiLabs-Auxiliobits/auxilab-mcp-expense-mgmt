"""Canonical enums shared across tools, API, and workers (SCOPING §20.A, §F)."""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    """The 8 expense categories the classifier may return (SCOPING §20.A)."""

    MEALS_ENTERTAINMENT = "Meals & Entertainment"
    TRAVEL_AIR = "Travel - Air"
    TRAVEL_HOTEL = "Travel - Hotel"
    TRAVEL_GROUND = "Travel - Ground"
    OFFICE_SUPPLIES = "Office Supplies"
    SOFTWARE_SUBSCRIPTIONS = "Software / Subscriptions"
    CLIENT_ENTERTAINMENT = "Client Entertainment"
    OTHER = "Other"


class PolicyCheckStatus(StrEnum):
    """Outcome of the deterministic intake policy check (Line 1)."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"  # non-blocking issues (e.g. classifier disagreement)


class RecommendedAction(StrEnum):
    ACCEPT = "accept"
    RETURN_TO_EMPLOYEE = "return_to_employee"
    REQUEST_RECEIPT = "request_receipt"


class DuplicateRisk(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"  # exact (employee, receipt_datetime, total) match → block


class SheetStatus(StrEnum):
    """Expense-sheet state machine (SCOPING §5.1, §F)."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IN_MANAGER_REVIEW = "IN_MANAGER_REVIEW"
    RETURNED_TO_EMPLOYEE = "RETURNED_TO_EMPLOYEE"
    IN_FINANCE_REVIEW = "IN_FINANCE_REVIEW"
    FINANCE_APPROVED = "FINANCE_APPROVED"
    FINANCE_REJECTED = "FINANCE_REJECTED"
    FINANCE_MANUAL_REVIEW = "FINANCE_MANUAL_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"


class LineItemStatus(StrEnum):
    """Per-line-item status (SCOPING §5.1, §F)."""

    PENDING_MANAGER = "PENDING_MANAGER"
    MANAGER_APPROVED = "MANAGER_APPROVED"
    MANAGER_REJECTED = "MANAGER_REJECTED"
    INFO_REQUESTED = "INFO_REQUESTED"
    POLICY_PASS = "POLICY_PASS"
    POLICY_FAIL = "POLICY_FAIL"
    POLICY_UNCERTAIN = "POLICY_UNCERTAIN"


class FinanceDecision(StrEnum):
    """LLM Finance Approver sheet-level outcome (SCOPING §F)."""

    APPROVED = "APPROVED"
    REJECTED_WITH_COMMENTS = "REJECTED_WITH_COMMENTS"
    ROUTED_TO_HUMAN = "ROUTED_TO_HUMAN"
