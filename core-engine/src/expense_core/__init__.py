"""expense_core — framework-free expense compliance engine (SCOPING §4, §11).

The five deterministic/LLM-assisted tools plus their Pydantic I/O contracts.
Nothing here imports FastAPI, SQLModel, or any Azure SDK at module load time, so
the engine is unit-testable in isolation and publishable as `auxilab-mcp-expense-mgmt`.
"""

from expense_core.tools.category_classifier import classify_category
from expense_core.tools.duplicate_detector import detect_duplicates
from expense_core.tools.policy_checker import check_policy
from expense_core.tools.receipt_parser import parse_receipt
from expense_core.tools.report_summariser import summarise_report

__all__ = [
    "check_policy",
    "parse_receipt",
    "classify_category",
    "detect_duplicates",
    "summarise_report",
]
