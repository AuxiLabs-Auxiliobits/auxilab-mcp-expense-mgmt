"""TripSense MCP Server — AI-powered business travel expense management."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from backend.database.db import init_db
from backend.mcp_server.policy_engine import check_expense_claim, load_policy
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

server = Server("tripsense")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Register all TripSense MCP tools."""
    return [
        # ----------------------------------------------------------------
        # REQUIRED TOOL #1 — expense_policy_checker
        # ----------------------------------------------------------------
        Tool(
            name="expense_policy_checker",
            description=(
                "Validate a single expense claim against the company policy JSON config. "
                "Returns compliant status, specific policy rule violated, and recommended "
                "action: Auto-approve / Flag for review / Reject."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee identifier",
                    },
                    "merchant": {
                        "type": "string",
                        "description": "Merchant name",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Claim amount in USD",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Expense category — one of: Meals & Entertainment, "
                            "Travel - Air, Travel - Hotel, Travel - Ground, "
                            "Office Supplies, Software/Subscriptions, "
                            "Client Entertainment, Other"
                        ),
                    },
                    "claim_date": {
                        "type": "string",
                        "description": "Date of expense (ISO format YYYY-MM-DD)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of the expense",
                    },
                    "has_receipt": {
                        "type": "boolean",
                        "description": "Whether a receipt is attached",
                    },
                },
                "required": ["employee_id", "merchant", "amount", "category", "claim_date"],
            },
        ),

        # ----------------------------------------------------------------
        # REQUIRED TOOL #2 — receipt_parser
        # ----------------------------------------------------------------
        Tool(
            name="receipt_parser",
            description=(
                "Parse receipt text or image and return structured fields: merchant name, "
                "date, total amount, tax amount, line items, payment method. "
                "Flags reconciliation errors if total doesn't match line items + tax."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": (
                            "Path to receipt image file, OR raw receipt text prefixed "
                            "with 'text:' for direct text parsing (e.g. 'text: Marriott Hotels...')"
                        ),
                    },
                },
                "required": ["image_path"],
            },
        ),

        # ----------------------------------------------------------------
        # REQUIRED TOOL #3 — spend_category_classifier
        # ----------------------------------------------------------------
        Tool(
            name="spend_category_classifier",
            description=(
                "Classify an expense into one of 8 standard categories based on merchant "
                "name and description. Categories: Meals & Entertainment, Travel - Air, "
                "Travel - Hotel, Travel - Ground, Office Supplies, Software/Subscriptions, "
                "Client Entertainment, Other. Returns top category with confidence score."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "merchant_name": {
                        "type": "string",
                        "description": "Name of the merchant",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional expense description for better classification",
                    },
                },
                "required": ["merchant_name"],
            },
        ),

        # ----------------------------------------------------------------
        # REQUIRED TOOL #4 — duplicate_claim_detector
        # ----------------------------------------------------------------
        Tool(
            name="duplicate_claim_detector",
            description=(
                "Detect potential duplicate expense claims for an employee. "
                "Checks for same merchant + date + amount, or same merchant + amount "
                "within ±3 days. Returns duplicate_risk_score (0.0–1.0) and "
                "matched_claim_reference."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string"},
                    "merchant": {"type": "string"},
                    "amount": {"type": "number"},
                    "date": {
                        "type": "string",
                        "description": "Claim date (ISO YYYY-MM-DD or MM/DD/YYYY)",
                    },
                },
                "required": ["employee_id", "merchant", "amount", "date"],
            },
        ),

        # ----------------------------------------------------------------
        # REQUIRED TOOL #5 — expense_report_summariser
        # ----------------------------------------------------------------
        Tool(
            name="expense_report_summariser",
            description=(
                "Generate a comprehensive expense report for an employee and period. "
                "Returns total by category, policy violation count, total at risk "
                "(flagged claims), compliance rate %, and a manager-ready summary narrative."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "approval_token": {
                        "type": "string",
                        "description": "Approval token for the trip/expense period",
                    },
                },
                "required": ["approval_token"],
            },
        ),

        # ----------------------------------------------------------------
        # EXISTING TOOLS — kept for backwards compatibility
        # ----------------------------------------------------------------
        Tool(
            name="plan_trip_budget",
            description=(
                "Generate a budget breakdown by category (hotel, meals, transport, "
                "miscellaneous) for a business trip based on destination, duration, and purpose."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Trip destination city or region",
                    },
                    "duration_days": {
                        "type": "integer",
                        "description": "Number of days for the trip",
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Business purpose (client_meeting, conference, training, sales_visit, internal)",
                    },
                },
                "required": ["destination", "duration_days", "purpose"],
            },
        ),
        Tool(
            name="check_policy_compliance",
            description=(
                "Check whether a trip plan complies with company travel policy. "
                "Returns compliant boolean and list of violations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "trip_plan": {
                        "type": "object",
                        "description": "Trip plan with destination, duration_days, purpose, breakdown",
                    },
                    "employee_id": {
                        "type": "string",
                        "description": "Employee identifier",
                    },
                },
                "required": ["trip_plan", "employee_id"],
            },
        ),
        Tool(
            name="pre_approve_trip",
            description=(
                "Pre-approve a compliant trip and issue an approval token with budget cap and expiry."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "trip_plan": {
                        "type": "object",
                        "description": "Trip plan with destination, duration_days, purpose, breakdown",
                    },
                    "employee_id": {
                        "type": "string",
                        "description": "Employee identifier",
                    },
                },
                "required": ["trip_plan", "employee_id"],
            },
        ),
        Tool(
            name="reconcile_trip",
            description=(
                "Reconcile submitted receipts against a pre-approved trip. Returns "
                "matched/unmatched receipts, overage per category, and compliance_rate %."
            ),
            inputSchema={
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
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    handlers = {
        # Required 5 tools
        "expense_policy_checker": lambda a: check_expense_claim(
            claim={
                "employee_id": a["employee_id"],
                "merchant": a["merchant"],
                "amount": a["amount"],
                "category": a["category"],
                "claim_date": a["claim_date"],
                "description": a.get("description", ""),
                "has_receipt": a.get("has_receipt", True),
            }
        ),
        "receipt_parser": lambda a: parse_receipt(a["image_path"]),
        "spend_category_classifier": lambda a: classify_spend_category(
            a["merchant_name"], a.get("description", "")
        ),
        "duplicate_claim_detector": lambda a: detect_duplicate_claim(
            a["employee_id"], a["merchant"], a["amount"], a["date"]
        ),
        "expense_report_summariser": lambda a: generate_trip_report(a["approval_token"]),

        # Existing tools
        "plan_trip_budget": lambda a: plan_trip_budget(
            a["destination"], a["duration_days"], a["purpose"]
        ),
        "check_policy_compliance": lambda a: check_policy_compliance(
            a["trip_plan"], a["employee_id"]
        ),
        "pre_approve_trip": lambda a: pre_approve_trip(a["trip_plan"], a["employee_id"]),
        "reconcile_trip": lambda a: reconcile_trip(a["approval_token"], a["receipts"]),
        "generate_trip_report": lambda a: generate_trip_report(a["approval_token"]),
    }

    if name not in handlers:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    try:
        result = handlers[name](arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def main() -> None:
    """Run the TripSense MCP server over stdio."""
    init_db()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Entry point for the MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()