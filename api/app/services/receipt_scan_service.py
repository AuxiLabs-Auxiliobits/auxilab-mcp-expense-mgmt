"""Live receipt scanning (SCOPING §4, §7).

Azure Document Intelligence's **prebuilt-receipt** model returns *structured* fields
(MerchantName, Total, TotalTax, Subtotal, TransactionDate, Items[...]) — far more reliable
than re-parsing raw OCR text, which is what produced wrong totals (e.g. grabbing "Total 4
item(s)" → 4). We read those fields directly and reconcile deterministically; the model
never decides compliance.

When the receipt total can't be read or doesn't match the entered amount, we set
`human_intervention_required` so Finance reviews it — nothing is surfaced to the employee.

Offline (no `doc_intel_endpoint`): decode text receipts and use the engine's deterministic
parser, so the API still runs without the Azure extras.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.config import Settings
from app.schemas.dto import ReceiptScanOut, ScanLineItem
from expense_core.llm.gateway import LLMGateway
from expense_core.llm.providers import LocalEchoProvider
from expense_core.tools import parse_receipt

_TOLERANCE = Decimal("0.01")
_MONEY_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def scan_receipt(blob_uri: str, entered_amount: Decimal | None, settings: Settings) -> ReceiptScanOut:
    try:
        data = _read_blob(blob_uri, settings)
    except Exception as exc:  # noqa: BLE001
        return _flagged_unavailable(entered_amount, f"could not read receipt: {exc}")

    try:
        if settings.doc_intel_endpoint:
            structured = _scan_with_doc_intelligence(data, settings)
            if structured is not None:
                merchant, total, tax, subtotal, dt, items = structured
                return _finalize(merchant, total, tax, subtotal, dt, items, "document_intelligence", entered_amount)
        # Offline / no structured result: decode text + deterministic engine parser.
        text = data.decode("utf-8", errors="ignore")
        if not text.strip():
            return _flagged_unavailable(
                entered_amount,
                "No text extracted. Configure Azure Document Intelligence for image/PDF OCR.",
            )
        parsed = parse_receipt(text, _llm(settings))
        items = [ScanLineItem(description=li.description, amount=li.amount) for li in parsed.line_items]
        return _finalize(parsed.merchant, parsed.total, parsed.tax, None, parsed.receipt_datetime,
                         items, "text", entered_amount)
    except Exception as exc:  # noqa: BLE001 — scan is best-effort; never 500 the request
        return _flagged_unavailable(entered_amount, f"scan failed: {exc}")


# --------------------------------------------------------------------------- #
# Reconciliation + flagging (shared by the structured and text paths)
# --------------------------------------------------------------------------- #
def _finalize(merchant, total, tax, subtotal, dt, items, source, entered):  # noqa: PLR0913
    tax = tax or (Decimal("0") if total is not None else None)

    reconciles: bool | None = None
    delta: Decimal | None = None
    if total is not None:
        if items:
            basis = sum((i.amount for i in items), Decimal("0")) + (tax or Decimal("0"))
        elif subtotal is not None:
            basis = subtotal + (tax or Decimal("0"))
        else:
            basis = None
        if basis is not None:
            delta = total - basis
            reconciles = abs(delta) <= _TOLERANCE

    matches_entered: bool | None = None
    if entered is not None and total is not None:
        matches_entered = abs(total - entered) <= _TOLERANCE

    needs_review = total is None or (entered is not None and matches_entered is False)
    if total is None:
        reason = "Could not read the receipt total — manual check required."
    elif entered is not None and matches_entered is False:
        reason = f"Receipt total {total} does not match the entered amount {entered}."
    else:
        reason = None

    return ReceiptScanOut(
        source=source,
        merchant=merchant,
        total=total,
        tax=tax,
        subtotal=subtotal,
        receipt_datetime=dt,
        line_items=items,
        reconciles=reconciles,
        delta=delta,
        entered_amount=entered,
        matches_entered=matches_entered,
        human_intervention_required=needs_review,
        detail=reason,
    )


def _flagged_unavailable(entered: Decimal | None, detail: str) -> ReceiptScanOut:
    # Can't read it → Finance must look (don't silently pass).
    return ReceiptScanOut(
        source="unavailable", entered_amount=entered, human_intervention_required=True, detail=detail
    )


# --------------------------------------------------------------------------- #
# Document Intelligence — structured prebuilt-receipt fields
# --------------------------------------------------------------------------- #
def _scan_with_doc_intelligence(data: bytes, settings: Settings):
    from azure.ai.documentintelligence import DocumentIntelligenceClient  # noqa: PLC0415
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    client = DocumentIntelligenceClient(
        endpoint=settings.doc_intel_endpoint, credential=DefaultAzureCredential()
    )
    result = client.begin_analyze_document("prebuilt-receipt", body=data).result()
    if not getattr(result, "documents", None):
        return None  # no structured receipt → caller falls back to text

    fields = result.documents[0].fields or {}
    merchant = _field_text(fields.get("MerchantName"))
    total = _field_money(fields.get("Total"))
    tax = _field_money(fields.get("TotalTax"))
    subtotal = _field_money(fields.get("Subtotal"))
    if total is None and subtotal is not None:
        total = subtotal + (tax or Decimal("0"))
    dt = _field_datetime(fields.get("TransactionDate"), fields.get("TransactionTime"))

    items: list[ScanLineItem] = []
    items_field = fields.get("Items")
    for entry in (getattr(items_field, "value_array", None) or []):
        obj = getattr(entry, "value_object", None) or {}
        amount = _field_money(obj.get("TotalPrice")) or _field_money(obj.get("Price"))
        if amount is None:
            continue
        items.append(ScanLineItem(description=_field_text(obj.get("Description")) or "item", amount=amount))

    return merchant, total, tax, subtotal, dt, items


def _field_text(field) -> str | None:
    if field is None:
        return None
    return getattr(field, "value_string", None) or (getattr(field, "content", None) or None)


def _field_money(field) -> Decimal | None:
    if field is None:
        return None
    currency = getattr(field, "value_currency", None)
    if currency is not None and getattr(currency, "amount", None) is not None:
        return Decimal(str(currency.amount))
    number = getattr(field, "value_number", None)
    if number is not None:
        return Decimal(str(number))
    return _parse_money(getattr(field, "content", None))


def _parse_money(text: str | None) -> Decimal | None:
    if not text:
        return None
    m = _MONEY_RE.search(text.replace(",", ""))
    if not m:
        return None
    try:
        return Decimal(m.group(0))
    except InvalidOperation:
        return None


def _field_datetime(date_field, time_field) -> datetime | None:
    d = getattr(date_field, "value_date", None) if date_field is not None else None
    if d is None:
        return None
    t = getattr(time_field, "value_time", None) if time_field is not None else None
    return datetime.combine(d, t or time(0, 0))


def _read_blob(uri: str, settings: Settings) -> bytes:
    if uri.startswith("file:"):
        path = unquote(urlparse(uri).path)
        if os.name == "nt" and path.startswith("/"):
            path = path[1:]
        return Path(path).read_bytes()
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobClient  # noqa: PLC0415

    return BlobClient.from_blob_url(uri, credential=DefaultAzureCredential()).download_blob().readall()


def _llm(settings: Settings) -> LLMGateway:
    if settings.foundry_endpoint:
        from expense_core.llm.providers import AzureFoundryProvider  # noqa: PLC0415

        return AzureFoundryProvider(
            endpoint=settings.foundry_endpoint, deployment=settings.foundry_chat_deployment
        )
    return LocalEchoProvider()
