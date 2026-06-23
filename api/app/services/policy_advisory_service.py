"""RAG advisory (SCOPING §7, §9.2): retrieve the most relevant clause from the agency's
indexed policy doc in Azure AI Search and surface it as an *advisory* note. Advisory only —
the deterministic policy check decides; this never blocks (LLM advises, code decides).

Agency-trimmed (security): the query is filtered to the caller's `agency_id`. Lazy-imports
the Search SDK and returns no clause when Search isn't configured (offline) — so the API runs
without the Azure extras and the deterministic check is unaffected.
"""

from __future__ import annotations

from app.config import Settings
from app.schemas.dto import PolicyAdvisoryClause, PolicyAdvisoryOut


def advisory(query: str, agency_id: str | None, settings: Settings) -> PolicyAdvisoryOut:
    if not settings.search_endpoint or not agency_id:
        return PolicyAdvisoryOut(clause=None)
    try:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415
        from azure.search.documents import SearchClient  # noqa: PLC0415

        client = SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index_name,
            credential=DefaultAzureCredential(),
        )
        # Security trimming: only this agency's chunks (SCOPING §9).
        results = client.search(
            search_text=query or "expense policy",
            filter=f"agency_id eq '{agency_id}'",
            top=1,
        )
        for doc in results:
            version = doc.get("policy_version") or "current"
            content = str(doc.get("content") or "").strip()
            if content:
                return PolicyAdvisoryOut(
                    clause=PolicyAdvisoryClause(source=f"Agency policy {version}", text=content[:600])
                )
    except Exception:  # noqa: BLE001 — advisory is best-effort; never surface as an error
        return PolicyAdvisoryOut(clause=None)
    return PolicyAdvisoryOut(clause=None)
