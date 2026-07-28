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
import re
from urllib.parse import unquote, urlparse

from workers.config import Settings, load_settings
from workers.consumers.service_bus import run_consumer

logger = logging.getLogger(__name__)


# Defender for Storage writes its verdict to a blob index tag / metadata entry. Microsoft
# uses the key "Malware Scanning scan result" with values like "No threats found" /
# "Malicious"; we match on substrings to tolerate casing/formatting variations.
_SCAN_RESULT_KEYS = ("Malware Scanning scan result", "malwarescanningscanresult")
_MALICIOUS_MARKERS = ("malicious", "threats found", "infected", "threat detected")
_CLEAN_MARKERS = ("no threats found", "no threat", "clean")


def virus_scan(blob_uri: str, settings: Settings) -> None:
    """Reject malware before any parsing (SCOPING §6.1 file edge cases), fail-closed.

    Reads Microsoft Defender for Storage's malware-scanning verdict, which is written to the
    blob's index tags / metadata. Offline (`file:` URI or no storage configured) → no-op.
    Azure: read the tags/metadata via the worker Managed Identity and
      - malicious verdict → raise (the consumer loop dead-letters the message);
      - "no threats found" → pass;
      - scan-result tag ABSENT → raise (fail-closed) unless `require_virus_scan` is False.
    """
    if blob_uri.startswith("file:") or not settings.storage_account_url:
        logger.debug("virus_scan (offline no-op) for %s", blob_uri)
        return

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobClient  # noqa: PLC0415

    client = BlobClient.from_blob_url(blob_uri, credential=DefaultAzureCredential())
    markers: dict[str, str] = {}
    try:
        markers.update(client.get_blob_tags() or {})
    except Exception as exc:  # noqa: BLE001 - tags may be unsupported; fall back to metadata
        logger.debug("get_blob_tags failed for %s: %s", blob_uri, exc)
    markers.update(client.get_blob_properties().metadata or {})

    verdict = _scan_verdict(markers)
    if verdict is None:
        if settings.require_virus_scan:
            raise RuntimeError(f"no malware-scan result for {blob_uri} — failing closed")
        logger.warning("No malware-scan result for %s; require_virus_scan=False, allowing", blob_uri)
        return
    if any(m in verdict for m in _MALICIOUS_MARKERS) and not any(
        c in verdict for c in _CLEAN_MARKERS
    ):
        raise RuntimeError(f"malware detected for {blob_uri}: {verdict!r}")
    logger.debug("virus_scan clean for %s: %r", blob_uri, verdict)


def _scan_verdict(markers: dict[str, str]) -> str | None:
    """Return the lowercased scan-result value from tags/metadata, or None if absent."""
    for key, value in markers.items():
        normalized = key.replace(" ", "").replace("_", "").lower()
        if any(normalized == k.replace(" ", "").lower() for k in _SCAN_RESULT_KEYS):
            return str(value).lower()
    return None


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

    if settings.doc_intel_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        credential = AzureKeyCredential(settings.doc_intel_api_key)
    else:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential()

    client = DocumentIntelligenceClient(
        endpoint=settings.doc_intel_endpoint, credential=credential
    )
    poller = client.begin_analyze_document("prebuilt-layout", body=data)
    result = poller.result()
    return result.content or ""


def chunk_text(text: str, *, max_chars: int = 1200) -> list[str]:
    """Split extracted policy text into retrieval chunks (SCOPING §7).

    Paragraph-aware but HARD-BOUNDED: no chunk exceeds `max_chars`, even when the extractor
    emits few/no blank-line breaks (Document Intelligence often returns one long block). This
    guarantees every chunk stays well under the embedding model's 8192-token input limit.
    Deterministic; safe to run offline.
    """
    # 1. Break into paragraphs; hard-split any paragraph longer than max_chars on whitespace.
    paras: list[str] = []
    for block in (p.strip() for p in text.split("\n\n")):
        if not block:
            continue
        if len(block) <= max_chars:
            paras.append(block)
            continue
        cur = ""
        for word in block.split():
            if len(cur) + len(word) + 1 > max_chars and cur:
                paras.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}" if cur else word
        if cur:
            paras.append(cur)

    # 2. Merge adjacent paragraphs up to max_chars.
    chunks: list[str] = []
    buffer = ""
    for para in paras:
        if len(buffer) + len(para) + 2 > max_chars and buffer:
            chunks.append(buffer)
            buffer = para
        else:
            buffer = f"{buffer}\n\n{para}" if buffer else para
    if buffer:
        chunks.append(buffer)

    # 3. Defensive final guard: hard-slice anything still over the limit (e.g. a single
    #    very long token with no whitespace), so no chunk can ever exceed max_chars.
    bounded: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            bounded.append(chunk)
        else:
            bounded.extend(chunk[i : i + max_chars] for i in range(0, len(chunk), max_chars))
    return bounded


def embed_chunks(chunks: list[str], settings: Settings) -> list[list[float]]:
    """Embed chunks via Azure AI Foundry / Azure OpenAI embeddings (SCOPING §7, §11).

    Uses the `openai` AzureOpenAI client, which builds the correct Azure OpenAI route
    (`{endpoint}/openai/deployments/{deployment}/embeddings`) for an AIServices/Foundry
    resource — `azure-ai-inference`'s EmbeddingsClient targets a different path and 404s
    against Foundry. Auth: a Foundry key if set, else Managed Identity / az-login (needs the
    "Cognitive Services OpenAI User" data role).

    Offline (no `foundry_endpoint`): return empty vectors — AI Search still keyword/semantic
    ranks on `content`, so retrieval degrades gracefully without vectors.
    """
    if not chunks:
        return []
    if not settings.foundry_endpoint:
        return [[] for _ in chunks]

    from openai import AzureOpenAI  # noqa: PLC0415

    common = {
        "azure_endpoint": settings.foundry_endpoint,
        "api_version": settings.embedding_api_version,
    }
    if settings.foundry_api_key:
        client = AzureOpenAI(api_key=settings.foundry_api_key, **common)
    else:
        from azure.identity import (  # noqa: PLC0415
            DefaultAzureCredential,
            get_bearer_token_provider,
        )

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        client = AzureOpenAI(azure_ad_token_provider=token_provider, **common)

    # Embed in small batches so a single request stays well under the deployment's
    # tokens-per-minute limit (avoids 429s on large policies). The openai client also
    # retries 429s with backoff, so transient spikes still succeed.
    batch_size = 16
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        resp = client.embeddings.create(model=settings.embedding_deployment, input=batch)
        vectors.extend(list(item.embedding) for item in resp.data)
    return vectors


def _safe_key(value: str) -> str:
    """Make a string safe for an Azure AI Search document key (letters/digits/_-= only)."""
    return re.sub(r"[^A-Za-z0-9_\-=]", "_", value)


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
    # AI Search keys allow only letters, digits, _ - = — sanitize (e.g. dots in a
    # version like "2026.06"). agency_id/policy_version keep their raw values in their own
    # fields so the agency filter and version pin still match exactly.
    key_prefix = f"{_safe_key(agency_id)}__{_safe_key(policy_version)}"
    docs = []
    for i, content in enumerate(chunks):
        doc = {
            "id": f"{key_prefix}__{i}",
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
        virus_scan(blob_uri, settings)
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
