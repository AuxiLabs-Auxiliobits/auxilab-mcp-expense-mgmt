"""Golden-dataset regression evals for the classifier and receipt parser (SCOPING §11.2).

Offline and deterministic by construction (LocalEchoProvider + keyword/regex fallbacks),
so it is reproducible in CI and gates accuracy against ``evals/thresholds.json``.
Run with ``python -m expense_core.evals``.
"""

from __future__ import annotations

from expense_core.evals.runner import (
    CategoryMetrics,
    ReceiptMetrics,
    evaluate_category,
    evaluate_receipt,
    run,
)

__all__ = [
    "CategoryMetrics",
    "ReceiptMetrics",
    "evaluate_category",
    "evaluate_receipt",
    "run",
]
