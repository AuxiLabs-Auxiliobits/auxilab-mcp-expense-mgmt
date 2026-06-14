# auxilab-mcp-expense-mgmt (`expense_mcp`)

The **MCP server** for the expense-management platform (SCOPING §4, §11): it exposes the
five `expense_core` tools as **MCP tools** for AI agents, using the official Python
[MCP SDK](https://pypi.org/project/mcp/) (`mcp`, FastMCP).

The server is **stateless** (SCOPING §2 — "MCP tools stay stateless"): each tool calls
into the engine and returns the result. No database, no auth, no RBAC — those live in the
API/portal layer. Published on PyPI as **`auxilab-mcp-expense-mgmt`**.

## The five tools

| MCP tool | Engine fn | LLM? | Returns |
|---|---|---|---|
| `policy_checker` | `check_policy` | No — pure rules | `{status, violations[], recommended_action}` |
| `receipt_parser` | `parse_receipt` | Yes + deterministic reconciliation | `{merchant, receipt_datetime, total, tax, line_items[], payment_method, reconciles, delta}` |
| `category_classifier` | `classify_category` | Yes + keyword fallback | `{category, confidence, rationale}` |
| `duplicate_detector` | `detect_duplicates` | No — pure rules | `{risk_score, risk, matches[]}` |
| `report_summariser` | `summarise_report` | Narrative only; numbers deterministic | `{total_by_category, violation_count, total_at_risk, compliance_rate_pct, narrative}` |

Every money figure is recomputed in Python; the LLM advises, deterministic code decides.

## Runs offline

The LLM-using tools default to `expense_core`'s deterministic `LocalEchoProvider`, so the
server and its tests need **no Azure**. Pass `use_llm=true` to a tool to opt into a real
provider *when* Azure Foundry env vars are set (see `.env.example`); otherwise it stays
offline and never fails closed on missing credentials.

## Install (editable)

`expense_mcp` depends on the sibling `expense-core` package. From the monorepo root:

```bash
pip install -e ./core-engine          # provides expense_core
pip install -e ./mcp-server[dev]      # this package + pytest/ruff
```

For real Azure access, add the extra (pulls `expense-core[azure]`):

```bash
pip install -e "./mcp-server[azure]"
```

## Run over stdio

Any of these launch the server speaking MCP over **stdio**:

```bash
auxilab-mcp-expense-mgmt    # console script (see [project.scripts])
python -m expense_mcp       # module entry point
```

## Connect from an MCP host (e.g. Claude Desktop)

Add to the host's MCP config (Claude Desktop: `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "auxilab-mcp-expense-mgmt"
    }
  }
}
```

Or, without installing the console script, point at the module:

```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "python",
      "args": ["-m", "expense_mcp"]
    }
  }
}
```

The host discovers the five tools and can call them with typed arguments; each returns a
JSON object matching the contracts above.

## Test

```bash
cd mcp-server
pytest    # uses the SCOPING §20.E samples (Uber → Travel - Ground, Marriott reconciliation)
```
