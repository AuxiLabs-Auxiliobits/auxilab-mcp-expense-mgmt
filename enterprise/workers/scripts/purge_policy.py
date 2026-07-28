"""Inspect / purge policy chunks in the Azure AI Search index (SCOPING §7).

The ingestion pipeline upserts one search doc per chunk, keyed by
`{agency_id}__{policy_version}__{chunk_index}` and trimmed at retrieval time by `agency_id`
*only* (not by version). So if you seeded a throwaway doc (e.g. sample-policy.md as `v1`)
and later uploaded the real policy as another version, BOTH versions live under the same
agency and the stale one can still surface in answers. Use this to see what's in the index
and delete the chunks for a specific version.

Run from `api/` so `load_settings()` reads your api/.env WORKERS_* values (same as
seed_policy.py). Needs the [azure] extra + a Search data role (or WORKERS_SEARCH_API_KEY).

    cd api
    $env:PYTHONPATH = "..\\workers\\src"

    # 1. See every (agency, version) in the index with chunk counts:
    .\\.venv\\Scripts\\python.exe ..\\workers\\scripts\\purge_policy.py --list

    # 2. Narrow to one agency:
    .\\.venv\\Scripts\\python.exe ..\\workers\\scripts\\purge_policy.py --list --agency <agency_id>

    # 3. Preview a delete (dry-run — shows how many chunks would go):
    .\\.venv\\Scripts\\python.exe ..\\workers\\scripts\\purge_policy.py --agency <agency_id> --version v1

    # 4. Actually delete the stale version's chunks:
    .\\.venv\\Scripts\\python.exe ..\\workers\\scripts\\purge_policy.py --agency <agency_id> --version v1 --yes
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workers.config import Settings, load_settings  # noqa: E402


def _escape_odata(value: str) -> str:
    """Escape single quotes for an OData string literal (injection-safe filter)."""
    return value.replace("'", "''")


def _client(settings: Settings):
    """Build a SearchClient against the configured index (key or Managed Identity)."""
    from azure.search.documents import SearchClient  # noqa: PLC0415

    if settings.search_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        credential = AzureKeyCredential(settings.search_api_key)
    else:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential()

    return SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=credential,
    )


def _list(client, agency_id: str | None) -> None:
    """Print every (agency_id, policy_version) present, with chunk counts."""
    flt = f"agency_id eq '{_escape_odata(agency_id)}'" if agency_id else None
    results = client.search(
        search_text="*", filter=flt, select=["agency_id", "policy_version"], top=1000
    )
    counts: Counter[tuple[str, str]] = Counter()
    for doc in results:
        counts[(doc.get("agency_id", "?"), doc.get("policy_version", "?"))] += 1

    if not counts:
        print("No matching documents in the index.")
        return
    print(f"{'agency_id':<40} {'version':<16} {'chunks':>6}")
    print("-" * 64)
    for (aid, ver), n in sorted(counts.items()):
        print(f"{aid:<40} {ver:<16} {n:>6}")
    print("\nThe stale seed (e.g. sample-policy.md) is usually the version with few chunks.")


def _ids_for(client, agency_id: str, version: str) -> list[str]:
    """Collect all chunk doc ids for one (agency_id, policy_version)."""
    flt = f"agency_id eq '{_escape_odata(agency_id)}' and policy_version eq '{_escape_odata(version)}'"
    return [doc["id"] for doc in client.search(search_text="*", filter=flt, select=["id"], top=1000)]


def _delete(client, agency_id: str, version: str, *, confirmed: bool) -> None:
    ids = _ids_for(client, agency_id, version)
    if not ids:
        print(f"No chunks found for agency={agency_id} version={version} — nothing to delete.")
        return
    if not confirmed:
        print(f"[dry-run] {len(ids)} chunk(s) match agency={agency_id} version={version}.")
        print("Re-run with --yes to delete them. Sample ids:")
        for i in ids[:5]:
            print(f"  {i}")
        return

    result = client.delete_documents(documents=[{"id": i} for i in ids])
    failed = [r for r in result if not r.succeeded]
    print(f"Deleted {len(ids) - len(failed)}/{len(ids)} chunk(s) for agency={agency_id} version={version}.")
    if failed:
        print(f"  {len(failed)} failed (e.g. {failed[0].key}: {failed[0].error_message}).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect / purge policy chunks in Azure AI Search.")
    parser.add_argument("--list", action="store_true", help="list (agency, version) + chunk counts")
    parser.add_argument("--agency", help="agency_id to scope --list, or to delete from")
    parser.add_argument("--version", help="policy_version to delete (requires --agency)")
    parser.add_argument("--yes", action="store_true", help="actually delete (default is dry-run)")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.search_endpoint:
        print("WORKERS_SEARCH_ENDPOINT is not set (check api/.env and run from api/).")
        return 2

    client = _client(settings)

    if args.version:
        if not args.agency:
            parser.error("--version requires --agency")
        _delete(client, args.agency, args.version, confirmed=args.yes)
    else:
        # Default action: list (optionally agency-scoped).
        _list(client, args.agency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
