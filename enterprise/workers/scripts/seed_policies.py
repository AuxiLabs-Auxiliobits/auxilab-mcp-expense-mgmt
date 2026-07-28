"""Bulk-seed per-agency policy documents into Azure AI Search (SCOPING §7, §17).

This is the fast path for demo/initial data: it reads local policy files, chunks + embeds
them, and upserts straight into the index — reusing the exact ingestion building blocks the
worker uses (so seeding and production ingestion stay identical).

    python workers/scripts/seed_policies.py ./policy_docs

Directory layout — ONE SUBFOLDER PER AGENCY, named by the agency's DB id:

    policy_docs/
      <agency_id>/                # e.g. the UUID from GET /admin/agencies
        version.txt               # optional; the policy_version string (default "v1")
        wifi.md                   # any number of .md/.txt policy files
        travel.md

IMPORTANT: the folder name MUST equal the agency_id used at decision time (the DB
`agencies.id`). Get the ids from `GET /admin/agencies` or the DB. The agency_id is the
security-trimming boundary — mis-naming a folder would file a policy under the wrong agency.

Offline (no WORKERS_SEARCH_ENDPOINT) this prints what it WOULD upsert, so you can dry-run
the layout before touching Azure. Production canonical path remains the API upload endpoint
(POST /finance/policies/{agency_id}) with maker-checker; this script is for bulk seeding.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script: make the package importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workers.config import load_settings  # noqa: E402
from workers.consumers.ingestion import chunk_text, embed_chunks, upsert_to_search  # noqa: E402

_DOC_GLOBS = ("*.md", "*.txt")


def seed_agency(agency_dir: Path, settings) -> int:
    agency_id = agency_dir.name
    version_file = agency_dir / "version.txt"
    policy_version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "v1"

    files = sorted(f for g in _DOC_GLOBS for f in agency_dir.glob(g))
    if not files:
        print(f"  [skip] {agency_id}: no .md/.txt files")
        return 0

    text = "\n\n".join(f.read_text(encoding="utf-8") for f in files)
    chunks = chunk_text(text)
    vectors = embed_chunks(chunks, settings)
    count = upsert_to_search(agency_id, policy_version, chunks, vectors, settings)
    mode = "azure" if settings.azure_search_enabled else "offline-dryrun"
    print(f"  [{mode}] {agency_id} v={policy_version}: {len(files)} file(s) -> {count} chunk(s)")
    return count


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("policy_docs")
    if not root.is_dir():
        raise SystemExit(f"policy docs root not found: {root}")

    settings = load_settings()
    print(f"Seeding from {root}  (search={'ON' if settings.azure_search_enabled else 'OFFLINE'})")
    total = sum(seed_agency(d, settings) for d in sorted(root.iterdir()) if d.is_dir())
    print(f"Done. {total} chunk(s) upserted.")


if __name__ == "__main__":
    main()
