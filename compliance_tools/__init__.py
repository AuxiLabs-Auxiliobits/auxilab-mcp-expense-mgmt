"""Five offline expense-compliance tools.

Everything in this package runs locally with no network, no credentials, and no cloud
services. The only hard dependency is ``pydantic``.

    >>> from compliance_tools import check_policy, load_policy
    >>> from compliance_tools.schemas import Category, LineItemInput
    >>> from datetime import date
    >>> from decimal import Decimal
    >>> item = LineItemInput(
    ...     employee_id="emp-001",
    ...     category=Category.MEALS_ENTERTAINMENT,
    ...     amount=Decimal("42.00"),
    ...     merchant="Noodle House",
    ...     expense_date=date.today(),
    ...     has_receipt=True,
    ... )
    >>> check_policy(item, load_policy()).status.value
    'pass'
"""

from __future__ import annotations

from compliance_tools.category_classifier import classify_category
from compliance_tools.duplicate_detector import detect_duplicates
from compliance_tools.llm import ChatMessage, LLMGateway, OfflineProvider
from compliance_tools.policy import BaselinePolicy, CapBoundary, load_policy
from compliance_tools.policy_checker import check_policy
from compliance_tools.receipt_parser import parse_receipt, parse_receipt_file
from compliance_tools.report_summariser import summarise_report
from compliance_tools.schemas import (
    CandidateLineItem,
    Category,
    CategoryResult,
    DuplicateMatch,
    DuplicateResult,
    DuplicateRisk,
    HistoricalLineItem,
    LineItemInput,
    ParsedLineItem,
    PolicyCheckStatus,
    PolicyResult,
    PolicyViolation,
    ReceiptParseResult,
    RecommendedAction,
    ReportSummary,
    SummaryLineItem,
)

__version__ = "1.1.0"

__all__ = [
    # The five tools
    "check_policy",
    "parse_receipt",
    "classify_category",
    "detect_duplicates",
    "summarise_report",
    # Convenience
    "parse_receipt_file",
    "load_policy",
    # Policy
    "BaselinePolicy",
    "CapBoundary",
    # LLM seam
    "LLMGateway",
    "ChatMessage",
    "OfflineProvider",
    # Schemas
    "CandidateLineItem",
    "Category",
    "CategoryResult",
    "DuplicateMatch",
    "DuplicateResult",
    "DuplicateRisk",
    "HistoricalLineItem",
    "LineItemInput",
    "ParsedLineItem",
    "PolicyCheckStatus",
    "PolicyResult",
    "PolicyViolation",
    "ReceiptParseResult",
    "RecommendedAction",
    "ReportSummary",
    "SummaryLineItem",
    "__version__",
]
