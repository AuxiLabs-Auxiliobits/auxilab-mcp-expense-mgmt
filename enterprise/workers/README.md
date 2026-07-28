# workers (`expense-workers`)

**Line 3 of the claim lifecycle** (SCOPING §6.3): the **LLM Finance Approver** — a
LangGraph worker — plus the **Service Bus consumers** that feed it and the
**agency-scoped RAG** retriever it reasons over. Bounded LLM authority with deterministic
guardrails (SCOPING §9.2): the model advises, math + route-to-human decide.

Like `expense-core`, nothing here imports Azure or LangGraph **at module load** — every
such dependency is lazy-imported behind an interface, so the package imports and the
offline `demo`/tests run with **no Azure** (`InMemoryRetriever`, `NoopShield`,
`LocalEchoProvider`).

## Architecture

```
Service Bus (finance-approval queue)         Service Bus (document-ingestion queue)
        │                                              │
        ▼                                              ▼
consumers/finance_queue.py                     consumers/ingestion.py
        │  approve_sheet(state)                        │  upload → virus scan → Doc Intel
        ▼                                              │  → chunk → embed → upsert to Search
finance_approver/runner.py ──► graph.py (LangGraph)    └─ (skeleton; lazy Azure TODOs)
        │
        ├─ rag/retriever.py        AgencyPolicyRetriever  → AzureSearch | InMemory (agency-trimmed)
        ├─ guardrails/prompt_shield.py  PromptShield      → AzureContentSafety | Noop
        └─ LLM gateway (expense_core)  LLMGateway         → AzureFoundry | LocalEcho
```

## How the approver maps to SCOPING §6.3 / §9.2

LangGraph nodes (`finance_approver/graph.py`):

| Node | SCOPING | Behaviour |
|---|---|---|
| `retrieve_policy` | §6.3, §7, §9.2 | Agency-trimmed RAG retrieval; Prompt-Shields each clause; empty/garbled policy → `policy_missing` |
| `route_to_human` *(conditional, interrupt)* | §6.3, §8 | Missing/ambiguous policy → `ROUTED_TO_HUMAN`; `interrupt_before` hook for checkpointed resume |
| `iterate_line_items` | §6.3, §8, §9.2 | **Per item** (never whole-sheet-in-one-prompt): cited LLM verdict **+** deterministic numeric cap check; per-sheet token budget |
| `aggregate` | §5, §6.3 | all pass → `APPROVED` · any fail → `REJECTED_WITH_COMMENTS` · any uncertain/missing → `ROUTED_TO_HUMAN` |

Guardrails (SCOPING §9.2) enforced per item:
- **Bounded authority** — no high-value ceiling (§19.5); the LLM may approve any amount when policy passes, but **can never override a hard numeric fail**.
- **Mandatory citation** — an uncitable / ungrounded verdict → `POLICY_UNCERTAIN` → route.
- **Deterministic numeric cross-check** — caps re-verified by `expense_core.BaselinePolicy.exceeds_cap` (inclusive boundary, §19.3); LLM disagreement with the math → route.
- **Reproducibility** — the result pins `model_version` + `policy_version` for audit/replay (§6.4).
- **Never silent-approve** — consumer errors retry/dead-letter; they never fall through to approved (§8, §14).

Cap boundary is **inclusive**: Wi-Fi **$100 passes**, **$100.01 fails** → whole sheet rejected (§20.E).

## Run the offline demo (no Azure, no LangGraph needed)

```bash
cd workers
pip install -e ".[dev]"          # pulls expense-core from ../core-engine
python -m workers demo
```

Reproduces the §20.E acceptance check on an in-memory sheet (Wi-Fi $100 passes, $100.01
fails → `REJECTED_WITH_COMMENTS`). Tests:

```bash
pytest
```

## Run the real consumers (production)

```bash
pip install -e ".[azure]"
cp .env.example .env            # fill in the WORKERS_* endpoints
python -m workers finance       # finance-approval queue → approve_sheet
python -m workers ingestion     # document-ingestion queue → RAG pipeline
```

Wiring is selected by configuration: set `WORKERS_SEARCH_ENDPOINT` /
`WORKERS_FOUNDRY_ENDPOINT` / `WORKERS_CONTENT_SAFETY_ENDPOINT` to swap each fallback for
its Azure implementation (`AzureSearchRetriever`, `AzureFoundryProvider`,
`AzureContentSafetyShield`). Managed Identity is used when no API key is given.

## Layout

```
src/workers/
  config.py                       # pydantic-settings (WORKERS_ prefix); offline defaults
  rag/retriever.py                # AgencyPolicyRetriever: AzureSearch | InMemory (agency-trimmed)
  guardrails/prompt_shield.py     # PromptShield: AzureContentSafety | Noop
  finance_approver/
    state.py                      # FinanceApproverState, verdicts, SheetResult
    graph.py                      # LangGraph nodes + dependency-free run_approver
    runner.py                     # approve_sheet(state) -> SheetResult
  consumers/
    service_bus.py                # generic receive/retry/dead-letter loop (no silent-approve)
    finance_queue.py              # finance-approval queue → approve_sheet
    ingestion.py                  # document-ingestion pipeline skeleton
  __main__.py                     # CLI: finance | ingestion | demo
tests/test_finance_approver.py    # §20.E acceptance + route-to-human + agency trimming
```
