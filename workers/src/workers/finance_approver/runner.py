"""approve_sheet — compile + invoke the approver graph (SCOPING §6.3, §11).

A plain function the API/consumer calls and tests exercise directly. It prefers the
compiled LangGraph (durable, checkpointable) and transparently falls back to the
dependency-free `run_approver` path when langgraph is not installed — so the offline
`demo` and tests behave identically to production.
"""

from __future__ import annotations

from expense_core.llm.gateway import LLMGateway
from expense_core.llm.providers import LocalEchoProvider

from workers.finance_approver.graph import build_graph, run_approver
from workers.finance_approver.state import FinanceApproverState, SheetResult
from workers.guardrails.prompt_shield import NoopShield, PromptShield
from workers.rag.retriever import AgencyPolicyRetriever


def approve_sheet(
    state: FinanceApproverState,
    *,
    retriever: AgencyPolicyRetriever,
    llm: LLMGateway | None = None,
    shield: PromptShield | None = None,
    checkpointer: object | None = None,
) -> SheetResult:
    """Run the Line 3 finance approver over one sheet and return its audit-ready result.

    Pins model + policy version into the result for reproducibility (SCOPING §6.4, §9.2).
    `retriever` must be agency-scoped; `llm` defaults to the offline LocalEchoProvider.
    """
    llm = llm or LocalEchoProvider()
    shield = shield or NoopShield()

    try:
        compiled = build_graph(
            retriever=retriever, llm=llm, shield=shield, checkpointer=checkpointer
        )
    except RuntimeError:
        # langgraph absent → dependency-free path with identical semantics.
        final = run_approver(state, retriever=retriever, llm=llm, shield=shield)
        return final.to_result()

    # A checkpointer requires a thread id on invoke (durable/resumable runs, SCOPING §11).
    invoke_config = (
        {"configurable": {"thread_id": state.sheet_id}} if checkpointer is not None else None
    )
    # LangGraph returns the channel state as a dict; re-hydrate into our Pydantic model.
    raw = compiled.invoke(state, config=invoke_config)
    final = (
        raw
        if isinstance(raw, FinanceApproverState)
        else FinanceApproverState.model_validate(raw)
    )
    return final.to_result()
