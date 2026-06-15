"""Finance-approval queue consumer (SCOPING §6.3, §11, §14).

Wires the Service Bus finance-approval queue to `approve_sheet`. Each message is a JSON
sheet payload (sheet_id, agency_id, line_items); the handler runs the LangGraph approver
and would persist the decision + emit the next workflow event. A handler failure propagates
to the consumer loop, which retries/dead-letters — it NEVER silent-approves (SCOPING §8).

Real Azure wiring (Search retriever, Foundry LLM, Prompt Shields) is built lazily and only
when the corresponding endpoints are configured; otherwise the offline fallbacks are used.
"""

from __future__ import annotations

import json
import logging

from expense_core.llm.gateway import LLMGateway
from expense_core.llm.providers import LocalEchoProvider

from workers.config import Settings, load_settings
from workers.consumers.service_bus import run_consumer
from workers.finance_approver.runner import approve_sheet
from workers.finance_approver.state import FinanceApproverState, SheetResult
from workers.guardrails.prompt_shield import NoopShield, PromptShield
from workers.rag.retriever import AgencyPolicyRetriever, InMemoryRetriever

logger = logging.getLogger(__name__)


def build_retriever(settings: Settings) -> AgencyPolicyRetriever:
    """Construct the agency retriever: Azure AI Search if configured, else in-memory."""
    if settings.azure_search_enabled:
        from workers.rag.retriever import AzureSearchRetriever  # noqa: PLC0415

        return AzureSearchRetriever(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index_name,
            api_key=settings.search_api_key or None,
        )
    logger.warning("No Search endpoint configured — using InMemoryRetriever (empty).")
    return InMemoryRetriever({})


def build_llm(settings: Settings) -> LLMGateway:
    """Construct the LLM gateway: Azure Foundry if configured, else LocalEcho."""
    if settings.azure_foundry_enabled:
        from expense_core.llm.providers import AzureFoundryProvider  # noqa: PLC0415

        return AzureFoundryProvider(
            endpoint=settings.foundry_endpoint,
            deployment=settings.foundry_deployment,
            api_key=settings.foundry_api_key or None,
            api_version=settings.embedding_api_version,
        )
    return LocalEchoProvider()


def build_shield(settings: Settings) -> PromptShield:
    """Construct the Prompt Shield: Azure Content Safety if configured, else Noop."""
    if settings.content_safety_enabled:
        from workers.guardrails.prompt_shield import AzureContentSafetyShield  # noqa: PLC0415

        return AzureContentSafetyShield(
            endpoint=settings.content_safety_endpoint,
            api_key=settings.content_safety_api_key or None,
        )
    return NoopShield()


def handle_sheet(
    body: str,
    *,
    retriever: AgencyPolicyRetriever,
    llm: LLMGateway,
    shield: PromptShield,
    settings: Settings,
) -> SheetResult:
    """Decode a queued sheet payload and run the approver (SCOPING §6.3).

    Raises on malformed input so the consumer loop dead-letters it rather than approving.
    """
    payload = json.loads(body)
    state = FinanceApproverState.model_validate(
        {
            **payload,
            "confidence_threshold": payload.get(
                "confidence_threshold", settings.confidence_routing_threshold
            ),
            "token_budget": payload.get("token_budget", settings.per_sheet_token_budget),
        }
    )
    result = approve_sheet(state, retriever=retriever, llm=llm, shield=shield)
    # Persist the decision via the API webhook, which writes the audit row and emits the
    # workflow event (FINANCE_APPROVED / FINANCE_REJECTED / FINANCE_MANUAL_REVIEW) carrying
    # model_version + policy_version + cited clauses (SCOPING §6.4). A failed POST propagates
    # so the consumer loop retries/dead-letters — it NEVER silent-approves (SCOPING §8).
    post_decision(result, settings)
    logger.info(
        "Sheet %s → %s (policy=%s model=%s conf=%.2f)",
        result.sheet_id, result.decision, result.policy_version,
        result.model_version, result.confidence,
    )
    return result


def _cited_clauses(result: SheetResult) -> list[str]:
    """The distinct policy clauses the verdicts cited, in first-seen order (SCOPING §6.4)."""
    clauses: list[str] = []
    for verdict in result.line_item_verdicts:
        clause = verdict.cited_clause
        if clause and clause not in clauses:
            clauses.append(clause)
    return clauses


def post_decision(result: SheetResult, settings: Settings) -> None:
    """POST the approver decision to the API webhook (SCOPING §6.3, §6.4).

    Mirrors `callback_indexed` in ingestion.py: lazy-import httpx, no-op offline (empty
    `api_base_url`), authenticate as the AGENT principal, and `raise_for_status()` so a failed
    post propagates to the consumer loop (NEVER silent-approve, SCOPING §8). The body matches
    the API's `LlmDecisionRequest` (decision, model_version, policy_version, cited_clauses,
    confidence).
    """
    if not settings.api_base_url:
        logger.info(
            "llm-decision callback (offline no-op): sheet=%s decision=%s",
            result.sheet_id, result.decision,
        )
        return

    import httpx  # noqa: PLC0415

    url = (
        f"{settings.api_base_url.rstrip('/')}"
        f"/finance/sheets/{result.sheet_id}/llm-decision"
    )
    headers = {"Authorization": f"Bearer {settings.agent_token}"} if settings.agent_token else {}
    resp = httpx.post(
        url, headers=headers,
        json={
            "decision": result.decision.value,
            "model_version": result.model_version,
            "policy_version": result.policy_version,
            "cited_clauses": _cited_clauses(result),
            "confidence": result.confidence,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main(settings: Settings | None = None) -> None:
    """Start the finance-approval consumer (SCOPING §11, §14)."""
    settings = settings or load_settings()
    retriever = build_retriever(settings)
    llm = build_llm(settings)
    shield = build_shield(settings)

    def _handler(body: str) -> None:
        handle_sheet(body, retriever=retriever, llm=llm, shield=shield, settings=settings)

    run_consumer(settings.finance_queue_name, _handler, settings)
