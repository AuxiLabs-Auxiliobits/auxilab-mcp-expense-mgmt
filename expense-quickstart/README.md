# Expense Management MCP server (quickstart)

A minimal MCP server built by following the official tutorial
[**Build an MCP server**](https://modelcontextprotocol.io/docs/develop/build-server),
step-for-step — the expense equivalent of the doc's weather example.

Where the doc's weather server wraps the National Weather Service API, this one
wraps the **Expense Management FastAPI backend** (`http://localhost:8000`). The API
enforces auth / RBAC / agency-scope / audit; the MCP server adds no business logic.

> This is a single-file teaching reference. The full production server (60 tools,
> resources, prompts, token forwarding, annotations) lives in [`../mcp-server`](../mcp-server).

## Concepts used (from the doc)

- **`FastMCP("expense")`** — one server instance; type hints + docstrings become the tool schema.
- **Tools** — `@mcp.tool()` async functions: `login`, `list_my_expenses`, `get_expense`, `get_pending_approvals`.
- **stdio transport** — `mcp.run(transport="stdio")`; **never print to stdout** (logs go to stderr).

## Set up (uv, exactly as the doc shows)

```powershell
# from this folder
uv venv
.venv\Scripts\activate
uv sync          # installs mcp[cli] + httpx from pyproject.toml
```

## Run

Start the backend first (from the repo root, so it uses the seeded demo DB):

```powershell
uvicorn app.main:app --app-dir api --reload
```

Then run the MCP server:

```powershell
uv run expense.py
```

It will listen on stdio for an MCP host.

## Test with MCP Inspector

```powershell
npx @modelcontextprotocol/inspector --cli uv run expense.py --method tools/list
npx @modelcontextprotocol/inspector --cli uv run expense.py `
  --method tools/call --tool-name login `
  --tool-arg email=employee@demo.local --tool-arg password=demo
```

Drop `--cli` to open the interactive Inspector web UI.

## Connect to Claude for Desktop

Edit `%AppData%\Claude\claude_desktop_config.json` (create it if missing):

```json
{
  "mcpServers": {
    "expense": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\Ankit\\Documents\\Expense Management MCP Server\\expense-quickstart",
        "run",
        "expense.py"
      ],
      "env": {
        "EXPENSE_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Save and restart Claude for Desktop. Then try:
*"Log in as employee@demo.local with password demo, then show my expenses."*

> Tip: if `uv` isn't on Claude's PATH, use its absolute path (find it with `where uv`).
