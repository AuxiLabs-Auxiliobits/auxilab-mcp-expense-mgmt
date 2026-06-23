"""Live receipt scanning (SCOPING §4, §7). Azure Document Intelligence does OCR/extraction;
the engine's `parse_receipt` then runs the *deterministic* reconciliation (Σ items + tax ==
total) — the model never decides compliance. Everything is lazy-imported with an offline
fallback so the API runs without the Azure extras: text-based receipts decode directly, and
binary receipts return `source="unavailable"` (configure Document Intelligence for OCR).

Goes live purely by setting `APP_DOC_INTEL_ENDPOINT` (+ `APP_FOUNDRY_ENDPOINT` for the LLM
extraction); auth is the API's Managed Identity (DefaultAzureCredential).
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.config import Settings
from app.schemas.dto import ReceiptScanOut, ScanLineItem
from expense_core.llm.gateway import LLMGateway
from expense_core.llm.providers import LocalEchoProvider
from expense_core.tools import parse_receipt

_TOLERANCE = Decimal("0.01")


def scan_receipt(blob_uri: str, entered_amount: Decimal | None, settings: Settings) -> ReceiptScanOut:
    try:
        data = _read_blob(blob_uri, settings)
    except Exception as exc:  # noqa: BLE001 — surface as a soft result, not a 500
        return ReceiptScanOut(source="unavailable", entered_amount=entered_amount,
                              detail=f"could not read receipt: {exc}")

    text, source = _extract_text(data, settings)
    if not text.strip():
        return ReceiptScanOut(
            source="unavailable", entered_amount=entered_amount,
            detail="No text extracted. Configure Azure Document Intelligence for image/PDF OCR.",
        )

    parsed = parse_receipt(text, _llm(settings))
    matches = None if entered_amount is None else abs(parsed.total - entered_amount) <= _TOLERANCE
    return ReceiptScanOut(
        source=source,
        merchant=parsed.merchant,
        total=parsed.total,
        tax=parsed.tax,
        receipt_datetime=parsed.receipt_datetime,
        line_items=[ScanLineItem(description=li.description, amount=li.amount) for li in parsed.line_items],
        reconciles=parsed.reconciles,
        delta=parsed.delta,
        entered_amount=entered_amount,
        matches_entered=matches,
    )


def _read_blob(uri: str, settings: Settings) -> bytes:
    if uri.startswith("file:"):
        path = unquote(urlparse(uri).path)
        if os.name == "nt" and path.startswith("/"):
            path = path[1:]
        return Path(path).read_bytes()
    # Azure blob — read with the API's Managed Identity (Blob Data Contributor).
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobClient  # noqa: PLC0415

    return BlobClient.from_blob_url(uri, credential=DefaultAzureCredential()).download_blob().readall()


def _extract_text(data: bytes, settings: Settings) -> tuple[str, str]:
    """Return (text, source). Document Intelligence prebuilt-receipt when configured, else
    decode text-based receipts directly (offline)."""
    if settings.doc_intel_endpoint:
        from azure.ai.documentintelligence import DocumentIntelligenceClient  # noqa: PLC0415
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        client = DocumentIntelligenceClient(
            endpoint=settings.doc_intel_endpoint, credential=DefaultAzureCredential()
        )
        poller = client.begin_analyze_document("prebuilt-receipt", body=data)
        return (poller.result().content or ""), "document_intelligence"
    return data.decode("utf-8", errors="ignore"), "text"


def _llm(settings: Settings) -> LLMGateway:
    if settings.foundry_endpoint:
        from expense_core.llm.providers import AzureFoundryProvider  # noqa: PLC0415

        return AzureFoundryProvider(
            endpoint=settings.foundry_endpoint, deployment=settings.foundry_chat_deployment
        )
    return LocalEchoProvider()
