"""Document-ingestion queue consumer (SCOPING §7, §11, §14).

Agency-policy ingestion pipeline (SCOPING §7):

    upload → virus scan → Document Intelligence (extract) → chunk → embed (Foundry)
           → upsert to Azure AI Search with the `agency_id` filter field → callback API

Every external call lazy-imports its Azure SDK and has an offline fallback so the package
imports and runs without the `[azure]` extra: blobs are read from `file://` URIs, extraction
decodes text directly, embeddings are skipped, and the search upsert is logged. A failure
raises so the consumer loop retries/dead-letters — a policy doc must never be silently
half-indexed (SCOPING §14).
"""

from __future__ import annotations

import json
import logging
from urllib.parse import unquote, urlparse

from workers.config import Settings, load_settings
from workers.consumers.service_bus import run_consumer

logger = logging.getLogger(__name__)


def virus_scan(blob_uri: str) -> None:
    """Reject malware before any parsing (SCOPING §6.1 file edge cases).

    TODO: call Defender for Storage / AV scan; raise on infection to dead-letter.
    """
    logger.debug("virus_scan stub for %s", blob_uri)


def download_blob(blob_uri: str, settings: Settings) -> bytes:
    """Fetch the raw document bytes. Offline reads `file://` URIs; Azure uses the worker's
    Blob Data Reader Managed Identity."""
    if blob_uri.startswith("file:"):
        from pathlib import Path  # noqa: PLC0415

        path = unquote(urlparse(blob_uri).path)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":  # Windows /C:/...
            path = path[1:]
        return Path(path).read_bytes()

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobClient  # noqa: PLC0415

    client = BlobClient.from_blob_url(blob_uri, credential=DefaultAzureCredential())
    return client.download_blob().readall()


def extract_document(blob_uri: str, settings: Settings) -> str:
    """OCR/layout extraction via Azure AI Document Intelligence (SCOPING §7, §13).

    Offline (no `doc_intel_endpoint`): decode the blob as UTF-8 text, so local `.txt`/`.md`
    policy docs ingest with zero infra. Azure: run the prebuilt-layout model.
    """
    data = download_blob(blob_uri, settings)
    if not settings.doc_intel_endpoint:
        return data.decode("utf-8", errors="ignore")

    from azure.ai.documentintelligence import DocumentIntelligenceClient  # noqa: PLC0415
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    client = DocumentIntelligenceClient(
        endpoint=settings.doc_intel_endpoint, credential=DefaultAzureCredential()
    )
    poller = client.begin_analyze_document("prebuilt-layout", body=data)
    result = poller.result()
    return result.content or ""


def chunk_text(text: str, *, max_chars: int = 1200) -> list[str]:
    """Split extracted policy text into retrieval chunks (SCOPING §7).

    Deterministic paragraph-aware splitter; safe to run offline.
    """
    chunks: list[str] = []
    buffer = ""
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if len(buffer) + len(para) + 2 > max_chars and buffer:
            chunks.append(buffer)
            buffer = para
        else:
            buffer = f"{buffer}\n\n{para}" if buffer else para
    if buffer:
        chunks.append(buffer)
    return chunks


def embed_chunks(chunks: list[str], settings: Settings) -> list[list[float]]:
    """Embed chunks via Azure AI Foundry embeddings (SCOPING §7, §11).

    Offline (no `foundry_endpoint`): return empty vectors — AI Search still keyword/semantic
    ranks on `content`, so retrieval degrades gracefully without vectors.
    """
    if not chunks:
        return []
    if not settings.foundry_endpoint:
        return [[] for _ in chunks]

    from azure.ai.inference import EmbeddingsClient  # noqa: PLC0415
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    client = EmbeddingsClient(
        endpoint=settings.foundry_endpoint, credential=DefaultAzureCredential()
    )
    resp = client.embed(input=chunks, model=settings.embedding_deployment)
    return [list(item.embedding) for item in resp.data]


def upsert_to_search(
    agency_id: str,
    policy_version: str,
    chunks: list[str],
    vectors: list[list[float]],
    settings: Settings,
) -> int:
    """Upsert chunks into the per-agency AI Search index (SCOPING §7).

    Each doc carries `agency_id` (the security-trimming filter field) + `policy_version` so
    retrieval can agency-trim and version-pin. The key is deterministic on
    (agency_id, policy_version, chunk_index) so re-ingesting a version is idempotent.
    Returns the number of chunks upserted. Offline: logs and returns the count.
    """
    docs = []
    for i, content in enumerate(chunks):
        doc = {
            "id": f"{agency_id}__{policy_version}__{i}",
            "agency_id": agency_id,
            "policy_version": policy_version,
            "chunk_index": i,
            "content": content,
        }
        if i < len(vectors) and vectors[i]:
            doc["content_vector"] = vectors[i]
        docs.append(doc)

    if not settings.azure_search_enabled:
        logger.info(
            "upsert_to_search (offline): agency=%s version=%s chunks=%d",
            agency_id, policy_version, len(docs),
        )
        return len(docs)

    from azure.search.documents import SearchClient  # noqa: PLC0415

    credential = _search_credential(settings)
    client = SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=credential,
    )
    client.merge_or_upload_documents(documents=docs)
    return len(docs)


def _search_credential(settings: Settings):
    if settings.search_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        return AzureKeyCredential(settings.search_api_key)
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    return DefaultAzureCredential()


def callback_indexed(
    policy_id: str | None, indexed: bool, chunks: int, detail: str | None, settings: Settings
) -> None:
    """Tell the API the ingestion result so it can stamp `AgencyPolicy.indexed_at`.

    No-op offline (no `api_base_url`). Authenticated as the AGENT principal.
    """
    if not policy_id or not settings.api_base_url:
        logger.info("indexed callback (offline no-op): policy=%s indexed=%s", policy_id, indexed)
        return

    import httpx  # noqa: PLC0415

    url = f"{settings.api_base_url.rstrip('/')}/finance/policies/{policy_id}/indexed"
    headers = {"Authorization": f"Bearer {settings.agent_token}"} if settings.agent_token else {}
    resp = httpx.post(
        url, headers=headers,
        json={"indexed": indexed, "chunks": chunks, "detail": detail}, timeout=30,
    )
    resp.raise_for_status()


def ingest_document(body: str, settings: Settings) -> None:
    """End-to-end ingestion for one policy document (SCOPING §7).

    Message payload: {agency_id, policy_version, blob_uri, policy_id?}. Raises on any failure
    so the consumer loop retries/dead-letters rather than indexing a partial document; on a
    terminal failure it best-effort reports the failure back to the API.
    """
    payload = json.loads(body)
    agency_id = payload["agency_id"]
    policy_version = payload["policy_version"]
    blob_uri = payload["blob_uri"]
    policy_id = payload.get("policy_id")

    try:
        virus_scan(blob_uri)
        text = extract_document(blob_uri, settings)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("no extractable policy text — nothing to index")
        vectors = embed_chunks(chunks, settings)
        count = upsert_to_search(agency_id, policy_version, chunks, vectors, settings)
    except Exception as exc:  # noqa: BLE001 - report failure, then re-raise to dead-letter
        callback_indexed(policy_id, False, 0, str(exc)[:500], settings)
        raise

    callback_indexed(policy_id, True, count, None, settings)
    logger.info("Ingested %s (agency=%s version=%s chunks=%d)",
                blob_uri, agency_id, policy_version, count)


def main(settings: Settings | None = None) -> None:
    """Start the document-ingestion consumer (SCOPING §11, §14)."""
    settings = settings or load_settings()

    def _handler(body: str) -> None:
        ingest_document(body, settings)

    run_consumer(settings.ingestion_queue_name, _handler, settings)
