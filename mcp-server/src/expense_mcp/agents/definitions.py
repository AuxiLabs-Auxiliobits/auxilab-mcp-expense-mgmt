"""Agent definitions exposed over MCP.

Each domain agent is registered as an MCP **prompt** generated from its `AgentSpec`. The MCP
host's model runs the prompt and performs the work through the listed MCP tools — so all
authorization/audit stays in the backend. An `orchestrator` prompt routes intent, and a
`recommend_agent` tool + `agents://catalog` resource let clients discover/route deterministically.
"""

from __future__ import annotations

import json
from typing import Any

from expense_mcp.agents.registry import AGENTS, AGENTS_BY_NAME, AgentSpec
from expense_mcp.agents.router import route
from expense_mcp.annotations import READ
from expense_mcp.instance import mcp

# Shared guardrails + response contract — identical across agents so behaviour is consistent.
_SECURITY = """\
Security & honesty rules (always):
- Perform business actions ONLY through the listed MCP tools. Never claim an action you didn't
  take via a tool, and never invent data — if a tool wasn't called, say so.
- Authorization is enforced by the backend. If a tool returns a permission error, stop and tell
  the user they're not allowed to do that — never try to work around it.
- Only use data returned for the signed-in user's scope. Do not request or expose another user's
  or agency's data.
- Before any consequential/irreversible action (approve, reject, return, withdraw, finance
  decision/override), confirm with the user first. Those tools are marked destructive."""

_RESPONSE_CONTRACT = """\
End every substantive reply with a short, structured footer:
- **Actions taken:** what you did (or "none — read-only").
- **Tools used:** the MCP tool names you called.
- **Data sources:** tools/resources the facts came from.
- **Rationale:** the business reason.
- **Confidence:** high / medium / low (when a judgement is involved).
- **Next steps:** what the user can do next."""


def render_agent(spec: AgentSpec) -> str:
    tools = "\n".join(f"  - {t}" for t in spec.tools)
    resources = "\n".join(f"  - {r}" for r in spec.resources) or "  - (none)"
    resp = "\n".join(f"  - {r}" for r in spec.responsibilities)
    return (
        f"You are the **{spec.title}** for the Expense Management platform.\n"
        f"Mission: {spec.role}\n\n"
        f"You may ONLY use these MCP tools (do not use tools outside this list):\n{tools}\n\n"
        f"Readable resources:\n{resources}\n\n"
        f"Responsibilities:\n{resp}\n\n"
        "How to work:\n"
        "  1. Confirm who you're acting as with `whoami` if the role/agency matters.\n"
        "  2. Gather facts with read tools/resources before acting.\n"
        "  3. For a multi-step task, do it step by step; if information is missing, ask one\n"
        "     concise clarifying question instead of guessing.\n"
        "  4. Take write actions only after confirming, and report exactly what each tool returned.\n\n"
        f"{_SECURITY}\n\n{_RESPONSE_CONTRACT}"
    )


# --- One MCP prompt per agent (names match the registry) ----------------------------------- #
@mcp.prompt(name="employee_agent")
def employee_agent() -> str:
    """Act as the Employee Agent (create/submit/track your own expenses)."""
    return render_agent(AGENTS_BY_NAME["employee_agent"])


@mcp.prompt(name="manager_agent")
def manager_agent() -> str:
    """Act as the Manager Agent (review/approve/reject/return sheets in your agency)."""
    return render_agent(AGENTS_BY_NAME["manager_agent"])


@mcp.prompt(name="finance_agent")
def finance_agent() -> str:
    """Act as the Finance Agent (resolve routed sheets, overrides, KPIs)."""
    return render_agent(AGENTS_BY_NAME["finance_agent"])


@mcp.prompt(name="admin_agent")
def admin_agent() -> str:
    """Act as the Admin Agent (users, dashboards, health, activity)."""
    return render_agent(AGENTS_BY_NAME["admin_agent"])


@mcp.prompt(name="policy_agent")
def policy_agent() -> str:
    """Act as the Policy Agent (answer policy questions, compare to policy, cite clauses)."""
    return render_agent(AGENTS_BY_NAME["policy_agent"])


@mcp.prompt(name="audit_agent")
def audit_agent() -> str:
    """Act as the Audit Agent (approval history, unusual activity, audit summaries)."""
    return render_agent(AGENTS_BY_NAME["audit_agent"])


@mcp.prompt(name="reporting_agent")
def reporting_agent() -> str:
    """Act as the Reporting Agent (spend analytics + KPI reports)."""
    return render_agent(AGENTS_BY_NAME["reporting_agent"])


@mcp.prompt(name="orchestrator")
def orchestrator() -> str:
    """Route a user's request to the right specialist agent and coordinate multi-agent work."""
    roster = "\n".join(f"  - **{a.title}** (`{a.name}`): {a.role}" for a in AGENTS)
    return (
        "You are the **Orchestrator** for a team of expense-management agents. For each user\n"
        "request: 1) identify intent (you may call the `recommend_agent` tool for a suggestion),\n"
        "2) adopt the matching agent's role and use ONLY that agent's tools, 3) for cross-domain\n"
        "asks, combine agents in sequence and attribute each part, 4) maintain context across\n"
        "turns (remember pending actions and prior answers), and 5) escalate to a human when\n"
        "confidence is low or a destructive action needs sign-off.\n\n"
        f"Available agents:\n{roster}\n\n"
        f"{_SECURITY}\n\n{_RESPONSE_CONTRACT}"
    )


# --- Deterministic routing tool + discovery resource --------------------------------------- #
@mcp.tool(annotations=READ)
def recommend_agent(query: str) -> dict[str, Any]:
    """Suggest which specialist agent should handle a request (deterministic router). Returns
    `{agent, title, confidence, rationale, suggested_tools, responsibilities}`. The model may
    override the suggestion."""
    r = route(query)
    return {
        "agent": r.agent, "title": r.title, "confidence": r.confidence,
        "rationale": r.rationale, "suggested_tools": r.suggested_tools,
        "responsibilities": r.responsibilities,
    }


@mcp.resource("agents://catalog")
def agents_catalog() -> str:
    """The agent roster + each agent's responsibilities and allowed MCP tools (for discovery)."""
    return json.dumps(
        [
            {"name": a.name, "title": a.title, "role": a.role,
             "responsibilities": a.responsibilities, "tools": a.tools, "resources": a.resources}
            for a in AGENTS
        ],
        indent=2,
    )
