"""Test the LLM Finance Approver end-to-end against the REAL Azure RAG + Foundry model.

    python workers/scripts/test_approve.py <agency_id> [line_items.json]

- <agency_id> must match a seeded folder/agency in the index (e.g. "crispin-EXAMPLE",
  or the real DB UUID once you've reseeded under UUIDs).
- line_items.json (optional): a JSON list of {id, category, amount, merchant, description}.
  Omit it to use a built-in sample (a Wi-Fi $100 item that should PASS Crispin's cap, and a
  Wi-Fi $120 item that should FAIL → whole sheet REJECTED_WITH_COMMENTS).

Wiring is driven entirely by WORKERS_* env: with the Search + Foundry endpoints set it uses
the real AzureSearchRetriever + AzureFoundryProvider; otherwise it degrades to the offline
fallbacks (so this same script is your local smoke test too).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workers.config import load_settings  # noqa: E402
from workers.consumers.finance_queue import build_llm, build_retriever, build_shield  # noqa: E402
from workers.finance_approver.runner import approve_sheet  # noqa: E402
from workers.finance_approver.state import ApproverLineItem, FinanceApproverState  # noqa: E402

_SAMPLE = [
    {"id": "li-1", "category": "Software / Subscriptions", "amount": "100.00",
     "merchant": "Comcast", "description": "Monthly Wi-Fi / internet reimbursement"},
    {"id": "li-2", "category": "Software / Subscriptions", "amount": "120.00",
     "merchant": "Comcast", "description": "Monthly Wi-Fi / internet reimbursement"},
]


def main() -> None:
    agency_id = sys.argv[1] if len(sys.argv) > 1 else "crispin-EXAMPLE"
    raw_items = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else _SAMPLE

    settings = load_settings()
    retriever = build_retriever(settings)
    llm = build_llm(settings)
    shield = build_shield(settings)

    print(f"Agency: {agency_id}")
    print(f"  Search : {'AZURE' if settings.azure_search_enabled else 'offline'}")
    print(f"  LLM    : {'AZURE ' + settings.foundry_deployment if settings.azure_foundry_enabled else 'offline echo'}\n")

    # Show what policy text was retrieved, so you can see whether the doc even covers the
    # expense you're testing (a travel policy may have no Wi-Fi clause, etc.).
    retrieved = retriever.retrieve(agency_id, " ".join(i.get("description", "") for i in raw_items))
    print(f"Retrieved {len(retrieved.clauses)} clause(s), policy_version={retrieved.policy_version}:")
    for c in retrieved.clauses[:3]:
        print(f"  • {c[:300].replace(chr(10), ' ')}")
    print()

    state = FinanceApproverState(
        sheet_id="TEST-SHEET",
        agency_id=agency_id,
        line_items=[ApproverLineItem.model_validate(i) for i in raw_items],
        confidence_threshold=settings.confidence_routing_threshold,
        token_budget=settings.per_sheet_token_budget,
    )
    result = approve_sheet(state, retriever=retriever, llm=llm, shield=shield)

    print(f"DECISION      : {result.decision}")
    print(f"policy_version: {result.policy_version}")
    print(f"model_version : {result.model_version}")
    print(f"confidence    : {result.confidence:.2f}\n")
    for v in result.line_item_verdicts:
        print(f"  - {v.line_item_id}: {v.status} (conf {v.confidence:.2f})")
        print(f"      reason: {v.reason}")
        if v.cited_clause:
            print(f"      cited : {v.cited_clause[:120]}")
    if result.comments:
        print("\ncomments:")
        for c in result.comments:
            print(f"  {c}")


if __name__ == "__main__":
    main()
