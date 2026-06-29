"""Policy Assistant — agency-scoped RAG over the agency's finance policy (SCOPING §7, §11).

Retrieval → generation, both agency-trimmed:
  • Retrieval: Azure AI Search (when `search_endpoint` is configured) filtered to the caller's
    agency; otherwise an offline retriever over the agency's stored policy document and the
    baseline ruleset.
  • Generation: Azure AI Foundry chat (when `foundry_endpoint` is configured), grounded ONLY
    in the retrieved clauses and required to cite them; otherwise a deterministic offline
    composer. When no clause covers the question, the assistant routes to a human (§6.3, §8).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.config import settings
from app.models.agency import Agency
from app.models.policy import AgencyPolicy
from app.principal import Principal
from app.storage import read_blob
from expense_core.llm.gateway import ChatMessage
from expense_core.llm.providers import AzureFoundryProvider, LocalEchoProvider
from expense_core.policy import load_baseline_policy

_STOPWORDS = {
    "the", "a", "an", "is", "are", "do", "does", "i", "we", "what", "whats", "how", "when",
    "and", "or", "of", "for", "to", "my", "need", "over", "amount", "much", "can", "with",
}


@dataclass
class Clause:
    id: str
    title: str
    text: str
    source: str


@dataclass
class AssistantAnswer:
    answer: str
    citations: list[Clause] = field(default_factory=list)
    policy_version: str = "baseline-v1"
    routed_to_human: bool = False
    model_version: str = "offline"


def answer_policy_question(session: Session, principal: Principal, query: str) -> AssistantAnswer:
    """Answer a policy question grounded in the caller's *own agency* policy only."""
    agency = session.get(Agency, principal.agency_id) if principal.agency_id else None
    agency_name = agency.name if agency else "your agency"

    clauses, policy_version = _retrieve(session, principal.agency_id, query)
    if not clauses:
        return AssistantAnswer(
            answer=(
                f"I couldn't find a clause in {agency_name}'s policy that covers that, so I've "
                "routed your question to a human reviewer."
            ),
            citations=[],
            policy_version=policy_version,
            routed_to_human=True,
        )

    if settings.azure_foundry_enabled:
        answer, model_version = _generate_foundry(query, clauses, agency_name)
    else:
        answer, model_version = _generate_offline(query, clauses, agency_name), "offline"

    return AssistantAnswer(
        answer=answer,
        citations=clauses,
        policy_version=policy_version,
        routed_to_human=False,
        model_version=model_version,
    )


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
def _retrieve(session: Session, agency_id: str | None, query: str) -> tuple[list[Clause], str]:
    if agency_id is None:
        return [], "none"
    if settings.azure_search_enabled:
        try:
            return _retrieve_azure(agency_id, query)
        except Exception:  # noqa: BLE001 — never fail the request on a search hiccup; fall back
            pass
    return _retrieve_offline(session, agency_id, query)


def _retrieve_azure(agency_id: str, query: str) -> tuple[list[Clause], str]:
    """Per-agency semantic retrieval via Azure AI Search (the agency's indexed Foundry policy),
    server-filtered to the agency and defensively re-trimmed (a misindexed doc can never leak
    another agency's clauses)."""
    from azure.search.documents import SearchClient  # noqa: PLC0415

    if settings.search_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        credential: object = AzureKeyCredential(settings.search_api_key)
    else:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential()

    client = SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=credential,
    )
    return _azure_search(client, agency_id, query)


def _azure_search(client, agency_id: str, query: str) -> tuple[list[Clause], str]:
    """Two-pass agency-scoped retrieval (mirrors the finance-approver retriever):
      1. semantic-ranked search for the question — best for natural-language policy queries;
      2. if that returns nothing (terms don't lexically/semantically match), fetch the agency's
         FULL policy so an answer is still grounded in *its* clauses, not the generic baseline.
    The agency filter is server-enforced AND re-checked per row (defense-in-depth, SCOPING §9.1)."""
    flt = f"agency_id eq '{agency_id.replace(chr(39), chr(39) * 2)}'"
    try:
        clauses, version = _azure_collect(client, agency_id, search_text=query, flt=flt, top=6, semantic=True)
    except Exception:  # noqa: BLE001 — service tier without semantic ranker → broad fetch below
        clauses, version = [], "unknown"
    if not clauses:
        clauses, version = _azure_collect(client, agency_id, search_text="*", flt=flt, top=50, semantic=False)
    return clauses, version


def _azure_collect(client, agency_id: str, *, search_text: str, flt: str, top: int, semantic: bool) -> tuple[list[Clause], str]:
    kwargs: dict = {"search_text": search_text or "*", "filter": flt, "top": top}
    if semantic:
        kwargs["query_type"] = "semantic"
        kwargs["semantic_configuration_name"] = settings.search_semantic_config
    rows = client.search(**kwargs)

    clauses: list[Clause] = []
    version = "unknown"
    for i, doc in enumerate(rows):
        if doc.get("agency_id") != agency_id:  # defense-in-depth (SCOPING §9.1)
            continue
        text = doc.get("content") or doc.get("clause") or ""
        if not text:
            continue
        version = doc.get("policy_version") or version
        clauses.append(
            Clause(id=f"C{i + 1}", title=doc.get("title") or "Policy clause",
                   text=text, source=f"{version} (AI Search)")
        )
    return clauses, version


def _retrieve_offline(session: Session, agency_id: str, query: str) -> tuple[list[Clause], str]:
    """Offline retrieval: prefer the agency's OWN stored policy document (if uploaded), topped up
    with the baseline ruleset. The agency's clauses always lead so the answer reflects that
    agency's policy, not the generic baseline."""
    agency_clauses, version = _agency_doc_clauses(session, agency_id)
    baseline = _baseline_clauses()

    agency_hits = _rank(query, agency_clauses)
    baseline_hits = _rank(query, baseline)
    combined = agency_hits + [c for c in baseline_hits if c not in agency_hits]

    # If the agency has a policy but nothing keyword-matched, still surface its clauses first
    # (ground in the agency's own policy). If there's no agency policy AND nothing matched, leave
    # it empty so the caller routes the question to a human (SCOPING §6.3, §8).
    if not agency_hits and agency_clauses:
        combined = agency_clauses[:2] + baseline_hits
    return combined[:4], version


def _agency_doc_clauses(session: Session, agency_id: str) -> tuple[list[Clause], str]:
    """Chunk the agency's most-recent uploaded policy document into clauses (empty if none)."""
    policy = session.exec(
        select(AgencyPolicy)
        .where(AgencyPolicy.agency_id == agency_id)
        .order_by(AgencyPolicy.version.desc())
    ).first()
    if not (policy and policy.doc_blob_uri):
        return [], "baseline-v1"
    try:
        text = read_blob(policy.doc_blob_uri).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001 — missing/unreadable blob → baseline only
        return [], "baseline-v1"
    version = f"agency-policy-v{policy.version}"
    clauses = [
        Clause(id=f"P{i + 1}", title="Agency policy", text=para,
               source=f"Agency policy v{policy.version}")
        for i, para in enumerate(_chunks(text))
    ]
    return clauses, version


def _baseline_clauses() -> list[Clause]:
    p = load_baseline_policy()
    meal = getattr(p, "per_meal_limit", None)
    hotel = getattr(p, "per_hotel_night_limit", None)
    receipt = getattr(p, "receipt_required_threshold", None)
    near = getattr(p, "duplicate_near_match_days", 2)
    out = [
        Clause("MEAL", "Per-meal limit",
               f"Meals are reimbursed up to ${meal} per meal, inclusive of tax and tip; "
               "amounts above the cap are rejected at intake.", "Baseline ruleset"),
        Clause("HOTEL", "Hotel per-night limit",
               f"Hotel lodging is capped at ${hotel} per night; multi-night stays are "
               "evaluated per night.", "Baseline ruleset"),
        Clause("RECEIPT", "Receipt requirement",
               f"A receipt is required on every line item; expenses over ${receipt} always "
               "require one before submission.", "Baseline ruleset"),
        Clause("DEADLINE", "Submission deadline",
               "Expense sheets must be submitted before the end of the calendar month in which "
               "the expense was incurred.", "Baseline ruleset"),
        Clause("DUPLICATE", "Duplicate detection",
               f"Duplicates are detected by matching employee, receipt date/time, and amount; "
               f"near-matches within {near} days are flagged and exact matches are blocked.",
               "Baseline ruleset"),
    ]
    return out


def _chunks(text: str) -> list[str]:
    paras = [c.strip() for c in text.replace("\r", "").split("\n") if c.strip()]
    return [c for c in paras if len(c) > 12][:30]


def _rank(query: str, pool: list[Clause]) -> list[Clause]:
    """Clauses from `pool` that match the query, best first (all score>0; caller caps)."""
    if not pool:
        return []
    terms = {t for t in _tokens(query) if t not in _STOPWORDS}
    if not terms:
        return list(pool)
    scored = [(sum(t in _tokens(c.title + " " + c.text) for t in terms), c) for c in pool]
    return [c for score, c in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0]


def _tokens(s: str) -> set[str]:
    return {w.strip(".,!?$%()/-").lower() for w in s.split() if w.strip()}


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _generate_foundry(query: str, clauses: list[Clause], agency_name: str) -> tuple[str, str]:
    provider = AzureFoundryProvider(
        endpoint=settings.foundry_endpoint,
        deployment=settings.foundry_chat_deployment,
        api_key=settings.foundry_api_key or None,
        api_version=settings.foundry_api_version,
    )
    context = "\n".join(f"[{c.id}] {c.title}: {c.text}" for c in clauses)
    system = ChatMessage(
        role="system",
        content=(
            "You are the expense Policy Assistant. Answer the user's question using ONLY the "
            f"policy clauses provided for {agency_name}. Cite the clause id(s) you used in "
            "square brackets. If the clauses do not cover the question, reply that you are "
            "routing it to a human reviewer. Be concise."
        ),
    )
    user = ChatMessage(role="user", content=f"Clauses:\n{context}\n\nQuestion: {query}")
    answer = provider.complete([system, user], temperature=0.0, max_tokens=600)
    return answer.strip(), provider.model_version


def _generate_offline(query: str, clauses: list[Clause], agency_name: str) -> str:
    top = clauses[:3]
    body = "\n".join(f"- **{c.title}** [{c.id}]: {c.text}" for c in top)
    return (
        f"Based on {agency_name}'s policy:\n\n{body}\n\n"
        "_If your situation isn't covered above, a human reviewer can help._"
    )
