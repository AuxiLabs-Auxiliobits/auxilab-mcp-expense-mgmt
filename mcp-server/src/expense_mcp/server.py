"""MCP server entry point — assembles the app and serves it over stdio.

Two tool layers (SCOPING §2, §11):
  • Engine tools (stateless): the five `expense_core` analysis tools — no auth/DB.
  • Business tools (stateful): authenticated adapters over the FastAPI backend. Each forwards
    the caller's bearer token so the API enforces JWT validation, RBAC, agency-scope, SoD, and
    audit — the MCP server adds no business logic of its own.

Importing the tool/resource/prompt modules registers them on the shared FastMCP instance.
The five engine handlers are re-exported here for back-compat with the existing test-suite.
"""

from __future__ import annotations

import logging

from expense_mcp.instance import mcp

# --- Register everything by importing the modules (side-effecting decorators) --------------- #
from expense_mcp.tools import (  # noqa: E402,F401
    approvals,
    assistant,
    auth_tools,
    dashboard,
    engine,
    expenses,
    finance,
    receipts,
    users,
)
from expense_mcp.resources import resources  # noqa: E402,F401
from expense_mcp.prompts import prompts  # noqa: E402,F401

# Back-compat re-exports (the engine tools were historically importable from `server`).
from expense_mcp.tools.engine import (  # noqa: E402,F401
    category_classifier,
    duplicate_detector,
    policy_checker,
    receipt_parser,
    report_summariser,
)


def main() -> None:
    """Console-script entry point: serve all tools/resources/prompts over stdio."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    mcp.run()


if __name__ == "__main__":
    main()
