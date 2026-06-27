"""RAG advisory (SCOPING §7, §9.2): retrieve the relevant clauses from the agency's indexed
policy doc in Azure AI Search, then have the LLM restate them in **plain English** for the
employee. Advisory only — the deterministic policy check decides; this never blocks (LLM
advises, code decides).

Agency-trimmed (security): the query is filtered to the caller's `agency_id`. Search + the
LLM are lazy-imported with offline fallbacks (no clause offline; a cleaned snippet if Search
is on but Foundry isn't), so the API runs without the Azure extras.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.schemas.dto import PolicyAdvisoryClause, PolicyAdvisoryOut

logger = logging.getLogger(__name__)


def _search_credential(settings: Settings):
    """Prefer the API key for local dev (no `az login` / managed identity needed); fall back to
    `DefaultAzureCredential` in Azure. Importing `azure.identity` lazily keeps it an optional
    dependency — only needed on the managed-identity path."""
    if settings.search_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        return AzureKeyCredential(settings.search_api_key)
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    return DefaultAzureCredential()


def advisory(query: str, agency_id: str | None, settings: Settings) -> PolicyAdvisoryOut:
    if not settings.search_endpoint or not agency_id:
        return PolicyAdvisoryOut(clause=None)
    try:
        from azure.search.documents import SearchClient  # noqa: PLC0415

        client = SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index_name,
            credential=_search_credential(settings),
        )
        # Security trimming: only this agency's chunks (SCOPING §9). Pull the top few so the
        # LLM has enough context to summarise accurately.
        results = client.search(
            search_text=query or "expense policy",
            filter=f"agency_id eq '{agency_id}'",
            top=3,
        )
        chunks: list[str] = []
        version = "current"
        for doc in results:
            version = doc.get("policy_version") or version
            content = str(doc.get("content") or "").strip()
            if content:
                chunks.append(content)
        if not chunks:
            return PolicyAdvisoryOut(clause=None)

        excerpt = "\n\n".join(chunks)[:1500]
        return PolicyAdvisoryOut(
            clause=PolicyAdvisoryClause(
                source=f"Agency policy {version}",
                text=_plain_language(query, excerpt, settings),
            )
        )
    except Exception:  # noqa: BLE001 — advisory is best-effort; never surface as an error
        # Best-effort: still return no clause, but log the cause so a misconfigured Search /
        # missing azure-identity / auth failure is diagnosable instead of a silent null.
        logger.warning("policy advisory retrieval failed (agency=%s)", agency_id, exc_info=True)
        return PolicyAdvisoryOut(clause=None)


def _plain_language(query: str, excerpt: str, settings: Settings) -> str:
    """Restate the retrieved policy in 1-2 plain sentences via Foundry; fall back to a
    cleaned one-line snippet of the source text when the LLM isn't configured/available."""
    if settings.foundry_endpoint:
        try:
            from expense_core.llm.gateway import ChatMessage  # noqa: PLC0415
            from expense_core.llm.providers import AzureFoundryProvider  # noqa: PLC0415

            llm = AzureFoundryProvider(
                endpoint=settings.foundry_endpoint,
                deployment=settings.foundry_chat_deployment,
                api_key=settings.foundry_api_key or None,
                api_version=settings.foundry_api_version,
            )
            out = llm.complete(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "You explain company expense policy to an employee in 1-2 short, "
                            "plain-English sentences. Use ONLY the provided policy text; never "
                            "invent limits or amounts. No preamble, no markdown, no quotes."
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=f"Expense being entered: {query}\n\nRelevant policy text:\n{excerpt}",
                    ),
                ],
                max_tokens=160,
            )
            if out and out.strip():
                return out.strip()
        except Exception:  # noqa: BLE001 — fall back to the snippet
            pass
    return _snippet(excerpt)


def _snippet(text: str) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:200] + ("…" if len(collapsed) > 200 else "")
