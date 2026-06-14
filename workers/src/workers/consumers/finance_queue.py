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
            endpoint=settings.foundry_endpoint, deployment=settings.foundry_deployment
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
    # TODO: persist `result` to the decisions table + emit the workflow event
    # (FINANCE_APPROVED / FINANCE_REJECTED / FINANCE_MANUAL_REVIEW), with the audit row
    # carrying model_version + policy_version + cited clauses (SCOPING §6.4).
    logger.info(
        "Sheet %s → %s (policy=%s model=%s conf=%.2f)",
        result.sheet_id, result.decision, result.policy_version,
        result.model_version, result.confidence,
    )
    return result


def main(settings: Settings | None = None) -> None:
    """Start the finance-approval consumer (SCOPING §11, §14)."""
    settings = settings or load_settings()
    retriever = build_retriever(settings)
    llm = build_llm(settings)
    shield = build_shield(settings)

    def _handler(body: str) -> None:
        handle_sheet(body, retriever=retriever, llm=llm, shield=shield, settings=settings)

    run_consumer(settings.finance_queue_name, _handler, settings)
