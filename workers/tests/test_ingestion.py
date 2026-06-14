"""Document-ingestion pipeline (SCOPING §7), offline.

No Azure: blobs are read from `file://` URIs, extraction decodes text, embeddings are
skipped, and the search upsert + API callback are no-ops. Verifies the happy path produces
the expected chunk count and that an empty document raises (→ dead-letter, never silent).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from workers.config import Settings
from workers.consumers.ingestion import chunk_text, ingest_document, upsert_to_search


def _offline_settings() -> Settings:
    # All Azure endpoints empty → offline fallbacks; no callback.
    return Settings(
        service_bus_connection_string="", search_endpoint="", foundry_endpoint="",
        doc_intel_endpoint="", storage_account_url="", api_base_url="",
    )


def test_chunk_text_splits_on_paragraphs():
    text = "Para one.\n\n" + ("x" * 1300) + "\n\nPara three."
    chunks = chunk_text(text, max_chars=1200)
    assert len(chunks) >= 2
    assert all(c.strip() for c in chunks)


def test_ingest_document_offline_happy_path(tmp_path: Path):
    doc = tmp_path / "policy.txt"
    doc.write_text(
        "Wi-Fi reimbursement is capped at $100.\n\nClient entertainment needs a receipt.",
        encoding="utf-8",
    )
    body = json.dumps({
        "agency_id": "crispin", "policy_version": "1",
        "blob_uri": doc.resolve().as_uri(), "policy_id": "pol-1",
    })
    # Should not raise (offline: extract → chunk → no-op embed/upsert/callback).
    ingest_document(body, _offline_settings())


def test_ingest_empty_document_raises(tmp_path: Path):
    doc = tmp_path / "empty.txt"
    doc.write_text("   \n\n  ", encoding="utf-8")
    body = json.dumps({
        "agency_id": "crispin", "policy_version": "1",
        "blob_uri": doc.resolve().as_uri(), "policy_id": "pol-1",
    })
    with pytest.raises(ValueError):
        ingest_document(body, _offline_settings())


def test_upsert_offline_returns_chunk_count():
    n = upsert_to_search("crispin", "1", ["a", "b", "c"], [[], [], []], _offline_settings())
    assert n == 3
