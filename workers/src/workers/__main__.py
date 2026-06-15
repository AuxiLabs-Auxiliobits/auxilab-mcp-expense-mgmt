"""CLI entry point for the workers package (SCOPING §11, §17, §20.E).

    python -m workers finance     # start the finance-approval consumer (needs [azure])
    python -m workers ingestion   # start the document-ingestion consumer (needs [azure])
    python -m workers demo        # run approve_sheet on an in-memory sample sheet, OFFLINE

The `demo` path uses InMemoryRetriever + LocalEcho + NoopShield and runs fully offline (no
Azure, no langgraph required). It reproduces the §20.E acceptance check: Wi-Fi $100 passes
(inclusive cap), $100.01 fails → whole sheet rejected.
"""

from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal

from expense_core.llm.providers import LocalEchoProvider

from workers.finance_approver.runner import approve_sheet
from workers.finance_approver.state import ApproverLineItem, FinanceApproverState
from workers.guardrails.prompt_shield import NoopShield
from workers.rag.retriever import InMemoryRetriever

_WIFI_CLAUSE = (
    "Wi-Fi / internet reimbursement is capped at $100; any amount above is rejected."
)


def _demo() -> int:
    """Run the offline §20.E acceptance demo and print the sheet decision."""
    retriever = InMemoryRetriever(
        {"crispin": [_WIFI_CLAUSE, "Client entertainment requires an itemised receipt."]},
        policy_version="crispin-2026.06",
    )
    state = FinanceApproverState(
        sheet_id="SHEET-DEMO-1",
        agency_id="crispin",
        line_items=[
            ApproverLineItem(
                id="li-1", category="Software / Subscriptions", amount=Decimal("100"),
                currency="USD", merchant="Comcast", description="Home Wi-Fi internet",
            ),
            ApproverLineItem(
                id="li-2", category="Software / Subscriptions", amount=Decimal("100.01"),
                currency="USD", merchant="Comcast", description="Home Wi-Fi internet",
            ),
        ],
    )

    result = approve_sheet(
        state, retriever=retriever, llm=LocalEchoProvider(), shield=NoopShield()
    )

    print(f"Sheet {result.sheet_id} (agency={result.agency_id})")
    print(f"  decision      : {result.decision}")
    print(f"  policy_version: {result.policy_version}")
    print(f"  model_version : {result.model_version}")
    print(f"  confidence    : {result.confidence:.2f}")
    print("  line items:")
    for v in result.line_item_verdicts:
        print(f"    - {v.line_item_id}: {v.status} | {v.reason}")
        if v.cited_clause:
            print(f"        cited: {v.cited_clause}")
    if result.comments:
        print("  comments:")
        for c in result.comments:
            print(f"    - {c}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argv = argv if argv is not None else sys.argv[1:]
    # The container selects its consumer via WORKER_CONSUMER (finance | ingestion); an
    # explicit CLI arg still wins. Falls back to the offline `demo` when neither is set.
    command = argv[0] if argv else os.environ.get("WORKER_CONSUMER", "demo")

    if command == "demo":
        return _demo()
    if command == "finance":
        from workers.consumers.finance_queue import main as finance_main  # noqa: PLC0415

        finance_main()
        return 0
    if command == "ingestion":
        from workers.consumers.ingestion import main as ingestion_main  # noqa: PLC0415

        ingestion_main()
        return 0

    print(f"Unknown command {command!r}. Use: finance | ingestion | demo", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
