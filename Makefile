# Convenience targets. On Windows use Git Bash, or run the underlying commands directly.
.PHONY: install test api workers mcp lint fmt up down

# Editable-install every Python package (engine first — others depend on it).
install:
	pip install -e ./core-engine[dev]
	pip install -e ./api[dev]
	pip install -e ./workers[dev]
	pip install -e ./mcp-server[dev]

# Run all Python test suites.
test:
	cd core-engine && pytest -q
	cd api && pytest -q
	cd workers && pytest -q
	cd mcp-server && pytest -q

api:            ## run the FastAPI API (SQLite, offline engine)
	cd api && uvicorn app.main:app --reload

workers:        ## run the offline finance-approver demo
	cd workers && python -m workers demo

mcp:            ## run the MCP server over stdio
	cd mcp-server && python -m expense_mcp

lint:
	ruff check core-engine api workers mcp-server

fmt:
	ruff format core-engine api workers mcp-server

up:             ## start local Postgres + Redis
	docker compose up -d

down:
	docker compose down
