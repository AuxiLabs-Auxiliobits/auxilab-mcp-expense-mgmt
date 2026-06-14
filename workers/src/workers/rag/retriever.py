"""Agency-scoped policy retrieval (SCOPING §7, §15).

The approver evaluates a sheet against **only the employee's agency** policy. Agency
trimming is a security boundary, not an optimisation: both implementations filter by
`agency_id` and the result is double-checked so a misconfigured index can never leak
another agency's clauses. Every result carries the `policy_version` it was drawn from so
the decision is version-pinned and reproducible (SCOPING §7, §9.2).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class RetrievedPolicy(BaseModel):
    """Agency-trimmed policy clauses + the version they were retrieved from."""

    agency_id: str
    policy_version: str
    clauses: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """No usable clauses → the approver must route to human (SCOPING §6.3, §8)."""
        return not any(c.strip() for c in self.clauses)


@runtime_checkable
class AgencyPolicyRetriever(Protocol):
    """Minimal surface the approver needs: agency-scoped policy retrieval."""

    def retrieve(self, agency_id: str, query: str, *, top_k: int = 6) -> RetrievedPolicy:
        """Return clauses for `agency_id` only, ranked for `query`."""
        ...


class InMemoryRetriever:
    """Offline/dev/test retriever — a dict of `agency_id -> [clause, ...]` (SCOPING §11).

    No Azure, fully deterministic. Enforces the same agency-trimming contract as the
    Azure implementation: an unknown agency yields an empty result (→ route to human).
    """

    def __init__(
        self,
        policies: dict[str, list[str]],
        *,
        policy_version: str = "inmemory-v1",
    ) -> None:
        self._policies = policies
        self._policy_version = policy_version

    def retrieve(self, agency_id: str, query: str, *, top_k: int = 6) -> RetrievedPolicy:
        # Agency trimming: only this agency's clauses, never another's.
        clauses = list(self._policies.get(agency_id, []))[:top_k]
        return RetrievedPolicy(
            agency_id=agency_id,
            policy_version=self._policy_version,
            clauses=clauses,
        )


class AzureSearchRetriever:
    """Per-agency hybrid + semantic retrieval via Azure AI Search (SCOPING §7).

    Lazy-imports `azure-search-documents` so the package imports without the `[azure]`
    extra. Retrieval is filtered server-side to `agency_id eq '<id>'` AND defensively
    re-trimmed client-side, so a misindexed document can never reach the approver.
    """

    def __init__(
        self,
        endpoint: str,
        index_name: str,
        *,
        api_key: str | None = None,
        credential: object | None = None,
        semantic_config: str = "default",
    ) -> None:
        try:
            from azure.search.documents import SearchClient  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover - exercised only with extras absent
            raise RuntimeError(
                "AzureSearchRetriever needs the 'azure' extra: pip install expense-workers[azure]"
            ) from e

        if credential is None:
            if api_key:
                from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

                credential = AzureKeyCredential(api_key)
            else:
                from azure.identity import DefaultAzureCredential  # noqa: PLC0415

                credential = DefaultAzureCredential()

        self._semantic_config = semantic_config
        self._client = SearchClient(
            endpoint=endpoint, index_name=index_name, credential=credential
        )

    def retrieve(self, agency_id: str, query: str, *, top_k: int = 6) -> RetrievedPolicy:
        # Hybrid (keyword + vector) + semantic ranker, filtered to the sheet's agency.
        # Agency filter is mandatory and server-enforced (SCOPING §7 agency trimming).
        agency_filter = f"agency_id eq '{_escape_odata(agency_id)}'"
        results = self._client.search(
            search_text=query,
            filter=agency_filter,
            query_type="semantic",
            semantic_configuration_name=self._semantic_config,
            top=top_k,
        )

        clauses: list[str] = []
        policy_version = "unknown"
        for doc in results:
            # Defense-in-depth: never trust the index filter alone (SCOPING §9.1).
            if doc.get("agency_id") != agency_id:
                continue
            content = doc.get("content") or doc.get("clause") or ""
            if content:
                clauses.append(content)
            policy_version = doc.get("policy_version") or policy_version

        return RetrievedPolicy(
            agency_id=agency_id,
            policy_version=policy_version,
            clauses=clauses,
        )


def _escape_odata(value: str) -> str:
    """Escape single quotes for an OData string literal (injection-safe filter)."""
    return value.replace("'", "''")
