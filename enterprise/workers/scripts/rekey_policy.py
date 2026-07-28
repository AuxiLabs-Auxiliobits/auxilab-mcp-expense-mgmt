"""Re-key policy chunks from one agency_id (and/or version) to another in Azure AI Search.

Retrieval trims by `agency_id`, and the chunk key is `{agency_id}__{policy_version}__{i}`,
so a doc ingested under the wrong agency id is invisible to that agency. This copies the
chunks (content + vector preserved — no re-embedding) under the correct agency id, then
optionally deletes the source copies. Idempotent on the target key.

Run from `api/` (so load_settings reads api/.env WORKERS_*), with the [azure] extra:

    cd api
    $env:PYTHONPATH = "..\\workers\\src"

    # dry-run (shows how many chunks would be copied):
    .\\.venv\\Scripts\\python.exe ..\\workers\\scripts\\rekey_policy.py `
        --from-agency e73551f9a91a4b59b29e9fbf602d8e1f --from-version 1 `
        --to-agency 77320a028c0f400b8f7f719287c6ff37 --to-version 1 --delete-source

    # apply: add --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workers.config import load_settings  # noqa: E402

# content_vector is not retrievable, so it can't be copied; retrieval ranks on `content`
# (semantic + keyword, with a full-policy fallback), so content-only re-keying is correct.
_COPY_FIELDS = ("chunk_index", "content")


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def _client(settings):
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


def _safe_key(value: str) -> str:
    import re  # noqa: PLC0415

    return re.sub(r"[^A-Za-z0-9_\-=]", "_", value)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Re-key policy chunks to a new agency id/version.")
    p.add_argument("--from-agency", required=True)
    p.add_argument("--from-version", required=True)
    p.add_argument("--to-agency", required=True)
    p.add_argument("--to-version", help="defaults to --from-version")
    p.add_argument("--delete-source", action="store_true", help="delete the source chunks after copy")
    p.add_argument("--yes", action="store_true", help="apply (default is dry-run)")
    args = p.parse_args(argv)
    to_version = args.to_version or args.from_version

    settings = load_settings()
    if not settings.search_endpoint:
        print("WORKERS_SEARCH_ENDPOINT is not set (check api/.env and run from api/).")
        return 2
    client = _client(settings)

    flt = (
        f"agency_id eq '{_escape_odata(args.from_agency)}' "
        f"and policy_version eq '{_escape_odata(args.from_version)}'"
    )
    source = list(client.search(search_text="*", filter=flt, select=["id", *_COPY_FIELDS], top=1000))
    if not source:
        print(f"No source chunks for agency={args.from_agency} version={args.from_version}.")
        return 0

    key_prefix = f"{_safe_key(args.to_agency)}__{_safe_key(to_version)}"
    new_docs = []
    for d in source:
        idx = d.get("chunk_index", 0)
        doc = {
            "id": f"{key_prefix}__{idx}",
            "agency_id": args.to_agency,
            "policy_version": to_version,
            "chunk_index": idx,
            "content": d.get("content", ""),
        }
        new_docs.append(doc)

    print(
        f"{'[apply]' if args.yes else '[dry-run]'} copy {len(new_docs)} chunk(s) "
        f"-> agency={args.to_agency} version={to_version}"
        + (" ; then DELETE source" if args.delete_source else "")
    )
    if not args.yes:
        print("Re-run with --yes to apply.")
        return 0

    up = client.merge_or_upload_documents(documents=new_docs)
    up_failed = [r for r in up if not r.succeeded]
    print(f"Upserted {len(new_docs) - len(up_failed)}/{len(new_docs)} chunk(s).")
    if up_failed:
        print(f"  {len(up_failed)} failed (e.g. {up_failed[0].key}: {up_failed[0].error_message}). Aborting delete.")
        return 1

    if args.delete_source:
        dl = client.delete_documents(documents=[{"id": d["id"]} for d in source])
        dl_failed = [r for r in dl if not r.succeeded]
        print(f"Deleted {len(source) - len(dl_failed)}/{len(source)} source chunk(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
