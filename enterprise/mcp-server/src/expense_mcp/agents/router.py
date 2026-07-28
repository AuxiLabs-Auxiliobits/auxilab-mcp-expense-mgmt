"""Deterministic intent → agent router.

A transparent, testable heuristic (keyword/phrase overlap) — NOT an LLM. The MCP host's model
can call `recommend_agent` to get a routing suggestion (which agent + first tools + rationale)
and is always free to override it. This keeps routing explainable and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass

from expense_mcp.agents.registry import AGENTS, AgentSpec

# Extra domain keywords per agent (beyond each agent's example intents).
_KEYWORDS: dict[str, list[str]] = {
    "employee_agent": ["my expense", "my sheet", "create", "draft", "submit", "resubmit",
                       "withdraw", "add line", "upload receipt", "returned to me"],
    "manager_agent": ["pending", "approve", "reject", "return to employee", "review queue",
                      "manager", "approval queue"],
    "finance_agent": ["finance", "override", "manual review", "anomaly", "routed"],
    "admin_agent": ["user", "users", "role", "health", "admin", "deactivate", "activity report"],
    "policy_agent": ["policy", "cap", "limit", "allowed", "rule", "deadline", "compliance", "violation"],
    "audit_agent": ["audit", "history", "trail", "suspicious", "unusual", "who approved"],
    "reporting_agent": ["report", "kpi", "spend", "category", "monthly", "analytics", "summary"],
}

# Tie-break priority when scores are equal (more specific domains first).
_PRIORITY = ["policy_agent", "audit_agent", "reporting_agent", "finance_agent",
             "manager_agent", "admin_agent", "employee_agent"]


@dataclass(frozen=True)
class Routing:
    agent: str
    title: str
    confidence: str  # "high" | "medium" | "low"
    rationale: str
    suggested_tools: list[str]
    responsibilities: list[str]


def _score(query: str, spec: AgentSpec) -> tuple[int, list[str]]:
    q = query.lower()
    hits: list[str] = []
    for phrase in spec.intents + _KEYWORDS.get(spec.name, []):
        if phrase.lower() in q:
            hits.append(phrase)
    return len(hits), hits


def route(query: str) -> Routing:
    """Pick the best-matching agent for a free-text request."""
    scored = [(_score(query, spec)[0], _score(query, spec)[1], spec) for spec in AGENTS]
    best_score = max(s for s, _, _ in scored) if scored else 0

    if best_score == 0:
        # No clear signal → orchestrator should ask a clarifying question.
        return Routing(
            agent="orchestrator",
            title="Orchestrator",
            confidence="low",
            rationale="No domain keyword matched; ask the user to clarify what they want to do.",
            suggested_tools=["recommend_agent"],
            responsibilities=["Clarify intent, then route to a domain agent."],
        )

    # Highest score; tie-break by priority order.
    candidates = [(spec, hits) for s, hits, spec in scored if s == best_score]
    candidates.sort(key=lambda c: _PRIORITY.index(c[0].name))
    spec, hits = candidates[0]
    confidence = "high" if best_score >= 2 else "medium"
    return Routing(
        agent=spec.name,
        title=spec.title,
        confidence=confidence,
        rationale=f"Matched {spec.title} on: {', '.join(hits[:4])}.",
        suggested_tools=spec.tools[:4],
        responsibilities=spec.responsibilities,
    )
