"""One-off local helper: ingest a single policy document into Azure AI Search for one
agency, so the `/intake/policy-advisory` + Policy Assistant retrieval have something to
return in local dev (SCOPING §7). Dev-only — production indexes via the Service Bus
ingestion worker.

The real ingestion pipeline runs with offline-safe fallbacks here: a `file://` blob URI
is read directly, virus scan + Document Intelligence are skipped, and (with no Foundry
endpoint set) embeddings are skipped — AI Search still keyword/semantic-ranks on `content`.

Prereq: create the index once (see workers/scripts/create_search_index.py). Run from the
`api/` dir so the worker config reads your api/.env WORKERS_* values:

    cd api
    $env:PYTHONPATH = "..\\workers\\src"
    .\\.venv\\Scripts\\python.exe ..\\workers\\seed_policy.py `
        --agency 77320a02028c0f400b8f7f719287c6ff37 `
        --version v1 `
        --file ..\\workers\\sample-policy.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workers.config import load_settings
from workers.consumers.ingestion import ingest_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest one policy doc into AI Search (local dev).")
    parser.add_argument("--agency", required=True, help="agency_id — MUST match the caller's JWT")
    parser.add_argument("--version", default="v1", help="policy_version label (default: v1)")
    parser.add_argument("--file", required=True, help="path to a .md/.txt policy document")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.search_endpoint:
        print("WORKERS_SEARCH_ENDPOINT is not set (check api/.env and run from api/).")
        return 2

    blob_uri = Path(args.file).resolve().as_uri()  # -> file:///C:/...
    ingest_document(
        json.dumps(
            {
                "agency_id": args.agency,
                "policy_version": args.version,
                "blob_uri": blob_uri,
                "policy_id": None,  # None → skips the API callback (no AgencyPolicy row to stamp)
            }
        ),
        settings,
    )
    print(f"Ingested {blob_uri}\n  agency={args.agency} version={args.version} index={settings.search_index_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
