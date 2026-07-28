"""The single FastMCP application instance.

Defined in its own module so every tool/resource/prompt module can import it without a
circular dependency on `server.py` (which only assembles + runs the app).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("auxilab-mcp-expense-mgmt")
