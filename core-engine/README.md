# core-engine (`expense_core`)

The framework-free heart of the platform (SCOPING §4, §11): the **five tools**, their
Pydantic v2 contracts, the baseline policy ruleset, and a model-agnostic LLM gateway.
No FastAPI, no SQLModel, no Azure SDK at import time — so it's unit-testable in isolation
and publishable as `auxilab-mcp-expense-mgmt`.

## The five tools

| Tool | Module | LLM? |
|---|---|---|
| Policy Checker | `tools/policy_checker.py` | No — pure rules |
| Receipt Parser | `tools/receipt_parser.py` | Yes + deterministic reconciliation |
| Category Classifier | `tools/category_classifier.py` | Yes + keyword fallback |
| Duplicate Detector | `tools/duplicate_detector.py` | No — pure rules |
| Report Summariser | `tools/report_summariser.py` | Narrative only; numbers deterministic |

**Governing principle:** the LLM advises, deterministic code decides. Every money
computation (reconciliation, caps, aggregation) is recomputed in Python and never trusted
from the model.

## Runs offline

The default `LocalEchoProvider` returns a sentinel; every LLM-using tool has a
deterministic fallback, so `pytest` and local dev need **no Azure**. Wire
`AzureFoundryProvider` (needs the `[azure]` extra) in production.

## Layout

```
src/expense_core/
  schemas/     enums.py, tools.py        # canonical enums + tool I/O contracts
  policy/      baseline.py + .json       # structured baseline ruleset (Admin-owned)
  llm/         gateway.py, providers.py  # LLMGateway protocol + providers
  tools/       the five tools
tests/         acceptance checks (SCOPING §20.E)
```

## Develop

```bash
cd core-engine
pip install -e ".[dev]"      # add ,azure for real Foundry access: ".[dev,azure]"
pytest
```
