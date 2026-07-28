"""Multi-agent layer tests — registry integrity, deterministic routing, prompt contracts, and
the discovery resource. No backend needed: these validate the agent definitions themselves
(the agents perform real work through the already-tested MCP tools)."""

from __future__ import annotations

import asyncio
import json

import pytest

from expense_mcp import server  # noqa: F401 - side-effect import, registers everything
from expense_mcp.agents import definitions
from expense_mcp.agents.registry import AGENTS, AGENTS_BY_NAME
from expense_mcp.agents.router import route
from expense_mcp.instance import mcp


def _registered_tool_names() -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}


def test_every_agent_tool_is_a_real_registered_tool():
    """No agent may reference a tool that doesn't exist (no phantom capabilities)."""
    registered = _registered_tool_names()
    for spec in AGENTS:
        missing = [t for t in spec.tools if t not in registered]
        assert not missing, f"{spec.name} references unknown tools: {missing}"


def test_seven_agents_plus_orchestrator_prompt_registered():
    prompts = {p.name for p in asyncio.run(mcp.list_prompts())}
    for spec in AGENTS:
        assert spec.name in prompts
    assert "orchestrator" in prompts


@pytest.mark.parametrize(
    "query, expected",
    [
        ("create an expense and submit it", "employee_agent"),
        ("show me pending approvals to review", "manager_agent"),
        ("approve sheet for my team", "manager_agent"),
        ("override the AI decision in the finance queue", "finance_agent"),
        ("what's the per-meal limit policy?", "policy_agent"),
        ("generate the monthly spend report by category", "reporting_agent"),
        ("show the audit trail and any suspicious activity", "audit_agent"),
        ("list users and system health", "admin_agent"),
    ],
)
def test_router_routes_intents(query, expected):
    assert route(query).agent == expected


def test_router_unknown_intent_falls_back_to_orchestrator():
    r = route("hello there")
    assert r.agent == "orchestrator" and r.confidence == "low"


def test_recommend_agent_tool_shape():
    out = definitions.recommend_agent("approve the pending expense sheet")
    assert out["agent"] == "manager_agent"
    assert out["confidence"] in ("high", "medium")
    assert set(out["suggested_tools"]).issubset(set(AGENTS_BY_NAME["manager_agent"].tools))
    assert out["rationale"]


def test_agent_prompts_contain_role_tools_security_and_contract():
    for spec in AGENTS:
        text = definitions.render_agent(spec)
        assert spec.title in text
        for tool in spec.tools:
            assert tool in text                      # allowed tools listed
        assert "Authorization is enforced by the backend" in text  # security guardrails
        assert "Actions taken:" in text              # response/explainability contract
        assert "ONLY use these MCP tools" in text or "ONLY" in text


def test_orchestrator_lists_all_agents():
    text = definitions.orchestrator()
    for spec in AGENTS:
        assert spec.title in text
    assert "recommend_agent" in text


def test_agents_catalog_resource_is_valid_json():
    data = json.loads(definitions.agents_catalog())
    assert len(data) == len(AGENTS)
    names = {a["name"] for a in data}
    assert names == set(AGENTS_BY_NAME)
    # the catalog exposes capabilities, not secrets
    assert all("tools" in a and "responsibilities" in a for a in data)
