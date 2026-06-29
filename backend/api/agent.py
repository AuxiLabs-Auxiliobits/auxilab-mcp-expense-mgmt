"""Chat agent — drives Claude (claude-sonnet-4-6) with the 8 TripSense MCP tools.

The Anthropic tool-use loop runs server-side so the API key never reaches the
browser. Claude decides autonomously which tools to call based on the user's
natural-language message; this module executes those calls against the same
tool functions the MCP server exposes and feeds the results back until Claude
produces a final answer.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from backend.mcp_server.tools.receipt_tools import (
    classify_spend_category,
    detect_duplicate_claim,
    parse_receipt,
)
from backend.mcp_server.tools.report_tools import generate_trip_report, reconcile_trip
from backend.mcp_server.tools.trip_tools import (
    check_policy_compliance,
    plan_trip_budget,
    pre_approve_trip,
)

# The user explicitly requested this model for the chat interface.
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

# Demo "current user" — tools that need an employee identifier default to this
# unless the user names someone else.
DEFAULT_EMPLOYEE_ID = "EMP-001"

SYSTEM_PROMPT = f"""You are TripSense, an AI assistant for business travel \
expense management. You help employees plan trips, check travel-policy \
compliance, pre-approve trips, parse receipts, classify spend, detect \
duplicate claims, reconcile trips, and generate expense reports.

You have access to 8 tools backed by the company's MCP server. Decide which \
tool(s) to call based on the user's request, and chain them when a task needs \
several steps (e.g. plan a budget, then check compliance, then pre-approve). \
When a follow-up message refers to "this trip", "it", or "my report", use the \
trip plan, approval token, or other data produced earlier in the conversation.

All monetary amounts are in Indian Rupees (₹, INR). Present figures with the ₹ \
symbol.

When a tool needs an employee_id and the user hasn't specified one, use \
"{DEFAULT_EMPLOYEE_ID}" (the current demo user). Prefer acting over asking: if \
you have enough information to call a tool, call it rather than asking the user \
to restate details. Keep replies concise and summarise tool results in plain \
language for the user."""


# Anthropic-format tool definitions — mirror backend/mcp_server/server.py.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "plan_trip_budget",
        "description": (
            "Generate a budget breakdown by category (hotel, meals, transport, "
            "miscellaneous) for a business trip based on destination, duration, "
            "and purpose."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Trip destination city or region"},
                "duration_days": {"type": "integer", "description": "Number of days for the trip"},
                "purpose": {
                    "type": "string",
                    "description": "Business purpose (client_meeting, conference, training, sales_visit, internal)",
                },
            },
            "required": ["destination", "duration_days", "purpose"],
        },
    },
    {
        "name": "check_policy_compliance",
        "description": (
            "Check whether a trip plan complies with company travel policy. "
            "Returns a compliant boolean and a list of violations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_plan": {
                    "type": "object",
                    "description": "Trip plan with destination, duration_days, purpose, breakdown",
                },
                "employee_id": {"type": "string", "description": "Employee identifier"},
            },
            "required": ["trip_plan", "employee_id"],
        },
    },
    {
        "name": "pre_approve_trip",
        "description": (
            "Pre-approve a compliant trip and issue an approval token with "
            "budget cap and expiry."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_plan": {
                    "type": "object",
                    "description": "Trip plan with destination, duration_days, purpose, breakdown",
                },
                "employee_id": {"type": "string", "description": "Employee identifier"},
            },
            "required": ["trip_plan", "employee_id"],
        },
    },
    {
        "name": "parse_receipt",
        "description": (
            "Parse a receipt image using OCR. Returns merchant, date, amount, "
            "line_items, ocr_confidence, and reconciliation_flag."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Path to the receipt image file"},
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "classify_spend_category",
        "description": "Classify an expense into a spend category based on merchant name and description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant_name": {"type": "string", "description": "Name of the merchant"},
                "description": {"type": "string", "description": "Optional expense description"},
            },
            "required": ["merchant_name"],
        },
    },
    {
        "name": "detect_duplicate_claim",
        "description": (
            "Detect potential duplicate expense claims. Checks for the same "
            "merchant and amount within ±3 days. Returns duplicate_risk_score "
            "and matched_claim_reference."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string"},
                "merchant": {"type": "string"},
                "amount": {"type": "number"},
                "date": {"type": "string", "description": "Claim date (ISO or MM/DD/YYYY)"},
            },
            "required": ["employee_id", "merchant", "amount", "date"],
        },
    },
    {
        "name": "reconcile_trip",
        "description": (
            "Reconcile submitted receipts against a pre-approved trip. Returns "
            "matched/unmatched receipts, overage per category, and compliance_rate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_token": {"type": "string"},
                "receipts": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of receipt dicts with merchant, amount, category, date",
                },
            },
            "required": ["approval_token", "receipts"],
        },
    },
    {
        "name": "generate_trip_report",
        "description": (
            "Generate a comprehensive trip expense report with totals by "
            "category, violation_count, total_at_risk, compliance_rate, and "
            "manager_narrative."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_token": {"type": "string"},
            },
            "required": ["approval_token"],
        },
    },
]

# Map tool name -> callable taking the tool input dict.
TOOL_HANDLERS = {
    "plan_trip_budget": lambda a: plan_trip_budget(
        a["destination"], a["duration_days"], a["purpose"]
    ),
    "check_policy_compliance": lambda a: check_policy_compliance(
        a["trip_plan"], a.get("employee_id", DEFAULT_EMPLOYEE_ID)
    ),
    "pre_approve_trip": lambda a: pre_approve_trip(
        a["trip_plan"], a.get("employee_id", DEFAULT_EMPLOYEE_ID)
    ),
    "parse_receipt": lambda a: parse_receipt(a["image_path"]),
    "classify_spend_category": lambda a: classify_spend_category(
        a["merchant_name"], a.get("description", "")
    ),
    "detect_duplicate_claim": lambda a: detect_duplicate_claim(
        a.get("employee_id", DEFAULT_EMPLOYEE_ID), a["merchant"], a["amount"], a["date"]
    ),
    "reconcile_trip": lambda a: reconcile_trip(a["approval_token"], a["receipts"]),
    "generate_trip_report": lambda a: generate_trip_report(a["approval_token"]),
}


def _execute_tool(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Run one tool call, returning its result (or an error dict)."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(tool_input)
    except Exception as exc:  # surface tool errors back to Claude, don't crash
        return {"error": str(exc)}


def run_agent(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the tool-use loop for one user turn.

    Args:
        messages: Full Anthropic-format conversation history, ending with the
            new user message.

    Returns:
        dict with the assistant's final text (`reply`), the list of tool calls
        made this turn (`tool_calls`), and the updated `messages` history to
        echo back to the client for the next turn.
    """
    client = anthropic.Anthropic()
    convo: list[dict[str, Any]] = list(messages)
    tool_calls_log: list[dict[str, Any]] = []

    # Loop until Claude stops requesting tools.
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=convo,
        )

        # Persist the assistant turn as plain dicts so it round-trips to the client.
        convo.append(
            {"role": "assistant", "content": [b.model_dump(mode="json") for b in response.content]}
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = _execute_tool(block.name, dict(block.input))
                tool_calls_log.append(
                    {"name": block.name, "input": block.input, "result": result}
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            convo.append({"role": "user", "content": tool_results})
            continue

        reply = "".join(b.text for b in response.content if b.type == "text")
        return {"messages": convo, "reply": reply, "tool_calls": tool_calls_log}
