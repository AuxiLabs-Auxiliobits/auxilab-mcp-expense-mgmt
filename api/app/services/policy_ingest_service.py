"""Inline (synchronous) policy RAG ingestion (SCOPING §7).

Normally a published policy doc is enqueued to Service Bus and a separate worker process
extracts → chunks → embeds → upserts it into the Azure AI Search index. In environments
where Service Bus isn't wired (local dev / single-box deploys) that async path is a no-op,
so the doc would never become RAG-searchable.

This module runs the same pipeline **inline** in the API process, reusing the worker's pure
ingestion functions (single source of truth — no duplicated chunking/upsert logic). It's
invoked from `policy_service.publish_policy` when `enqueue_ingestion` reports nothing was
sent and Azure Search is configured. Embedding is best-effort: if the embedding deployment
is unavailable, we index the chunks without vectors (AI Search still keyword/semantic ranks
on `content`), so a missing embeddings model never blocks indexing.
"""

from __future__ import annotations

import logging

from app.config import Settings

logger = logging.getLogger(__name__)


def _worker_settings(settings: Settings):
    """Build the worker's Settings from the API's config so the worker ingestion functions
    use the same Azure endpoints/keys the API already has (Search, Foundry, Doc Intelligence,
    Blob). Avoids depending on WORKERS_* env vars being separately populated."""
    from workers.config import Settings as WorkerSettings  # noqa: PLC0415

    return WorkerSettings(
        search_endpoint=settings.search_endpoint,
        search_index_name=settings.search_index_name,
        search_api_key=settings.search_api_key,
        foundry_endpoint=settings.foundry_endpoint,
        foundry_api_key=settings.foundry_api_key,
        doc_intel_endpoint=settings.doc_intel_endpoint,
        doc_intel_api_key=settings.doc_intel_api_key,
        storage_account_url=settings.storage_account_url,
        require_virus_scan=settings.require_virus_scan,
    )


def ingest_policy_inline(
    *, blob_uri: str, agency_id: str, policy_version: str, settings: Settings
) -> int:
    """Extract → chunk → embed → upsert one policy doc into the agency's AI Search index,
    synchronously. Returns the number of chunks upserted. Raises on a hard failure (no
    extractable text, search upsert error) so the caller can record POLICY_INDEX_FAILED."""
    from workers.consumers import ingestion as ing  # noqa: PLC0415

    ws = _worker_settings(settings)

    # file:// blobs (local dev) and no-storage envs make virus_scan a no-op; on real Blob it
    # reads the Defender verdict and fails closed.
    ing.virus_scan(blob_uri, ws)

    text = ing.extract_document(blob_uri, ws)
    chunks = ing.chunk_text(text)
    if not chunks:
        raise ValueError("no extractable policy text — nothing to index")

    # Embedding is best-effort: a missing/unavailable embeddings deployment must not block
    # indexing — AI Search still keyword/semantic ranks on the `content` field without vectors.
    try:
        vectors = ing.embed_chunks(chunks, ws)
    except Exception:  # noqa: BLE001
        logger.warning(
            "policy embedding failed (agency=%s version=%s) — indexing without vectors",
            agency_id, policy_version, exc_info=True,
        )
        vectors = [[] for _ in chunks]

    count = ing.upsert_to_search(agency_id, policy_version, chunks, vectors, ws)
    logger.info(
        "inline-ingested policy (agency=%s version=%s chunks=%d)",
        agency_id, policy_version, count,
    )
    return count


def extract_policy_text(blob_uri: str, settings: Settings) -> str:
    """Extract the full plain text of a policy doc (for the read-only viewer). Reuses the
    worker's Document Intelligence / text-decode extractor."""
    from workers.consumers import ingestion as ing  # noqa: PLC0415

    return ing.extract_document(blob_uri, _worker_settings(settings))


def purge_policy_chunks(agency_id: str, policy_version: str, settings: Settings) -> int:
    """Delete all Azure AI Search chunks for one (agency, version) pair.
    Returns the number of chunks deleted. No-op (returns 0) when Search is not configured."""
    if not settings.search_endpoint:
        return 0

    from azure.search.documents import SearchClient  # noqa: PLC0415

    if settings.search_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415
        credential = AzureKeyCredential(settings.search_api_key)
    else:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415
        credential = DefaultAzureCredential()

    client = SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=credential,
    )

    safe_agency = agency_id.replace("'", "''")
    safe_version = policy_version.replace("'", "''")
    ids = [
        doc["id"]
        for doc in client.search(
            search_text="*",
            filter=f"agency_id eq '{safe_agency}' and policy_version eq '{safe_version}'",
            select=["id"],
            top=1000,
        )
    ]
    if not ids:
        return 0

    results = client.delete_documents(documents=[{"id": i} for i in ids])
    failed = [r for r in results if not r.succeeded]
    if failed:
        raise RuntimeError(
            f"{len(failed)}/{len(ids)} chunk(s) failed to delete from Azure AI Search"
        )
    return len(ids)
