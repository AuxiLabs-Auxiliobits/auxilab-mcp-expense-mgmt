"""expense-workers — the LLM Finance Approver worker and async consumers (SCOPING §2, §11).

Line 3 of the claim lifecycle (SCOPING §6.3): a LangGraph worker that retrieves the
sheet's agency policy from RAG, iterates each line item with bounded LLM authority +
deterministic numeric cross-checks, and emits a sheet-level Approve / Reject-with-comments
/ Route-to-human decision. Service Bus consumers feed it and the ingestion pipeline.

Every Azure / LangGraph-Azure dependency is lazy-imported, so the package imports and the
offline `demo` / tests run with no Azure installed (InMemoryRetriever, NoopShield,
LocalEchoProvider).
"""

from workers.finance_approver.runner import approve_sheet
from workers.finance_approver.state import FinanceApproverState, SheetResult

__all__ = ["approve_sheet", "FinanceApproverState", "SheetResult"]
