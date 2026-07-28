"""Shared MCP tool annotations (spec hints the client uses to shape UX).

`readOnlyHint`     — no side effects (safe to call freely).
`destructiveHint`  — consequential/irreversible writes → clients should confirm first.
`idempotentHint`   — repeating the call has no extra effect.
`openWorldHint`    — touches an external system (the backend API) vs pure local compute.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

# Reads against the backend.
READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)

# Pure local computation (engine tools) — no external calls.
COMPUTE = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

# Creates/updates state (not destructive): create, add, update, submit, upload, login.
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)

# Consequential, hard-to-undo workflow actions (approve/reject/withdraw/override/decision).
# destructiveHint=True tells clients (Claude Desktop, etc.) to ask for confirmation first —
# important when an AI is driving approvals.
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
