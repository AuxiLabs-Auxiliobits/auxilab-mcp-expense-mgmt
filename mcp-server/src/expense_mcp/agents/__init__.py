"""Multi-agent layer.

Agents are realized as MCP **prompts** (role + allowed tools + workflow + guardrails) that the
MCP host's LLM enacts — the host (Claude Desktop / Cursor / ChatGPT) is the agent runtime. This
module adds NO business logic and NO LLM of its own: every business action still runs through the
existing MCP tools, so RBAC/agency-scope/SoD/audit are enforced by the backend exactly as before.

- registry.py    — the single source of truth: each agent's role, responsibilities, allowed tools.
- definitions.py — generates one MCP prompt per agent + an orchestrator prompt.
- router.py      — a transparent, deterministic intent → agent router (the `recommend_agent` tool).
"""
