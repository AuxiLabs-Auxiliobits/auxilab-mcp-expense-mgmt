"""Line 1 — Intake gate (SCOPING §6.1). Runs the deterministic engine tools over each
line item at submission, persists a ClaimCheck, and reports whether the sheet may proceed.

Beyond the policy/category/duplicate tools this gate also enforces, per line item:
  • a **malware scan** of every attached receipt (Defender for Storage; fail-closed), and
  • a **receipt reconciliation** — negative/over-total tax and a positive-total receipt whose
    Σ(items)+tax doesn't match the total are hard data errors that return the sheet to the
    employee; an unreadable receipt or an entered-amount mismatch is flagged for Finance
    (`needs_human_review`) without blocking the sheet (mirrors `receipt_scan_service`).

The LLM-using tools (classifier) default to the engine's offline provider here; wiring a
real Foundry gateway is a one-line injection when the worker/API needs it.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.config import settings
from app.models.attachment import Attachment, ScanStatus
from app.models.claim_check import ClaimCheck
from app.models.line_item import LineItem
from app.services import malware_scan_service, receipt_scan_service
from expense_core.policy import BaselinePolicy
from expense_core.schemas.enums import PolicyCheckStatus
from expense_core.schemas.tools import LineItemInput
from expense_core.tools import check_policy, classify_category, detect_duplicates
from expense_core.tools.duplicate_detector import CandidateLineItem, HistoricalLineItem


def run_intake(session: Session, item: LineItem, policy: BaselinePolicy) -> ClaimCheck:
    """Run policy + classifier + duplicate + malware-scan + reconciliation checks for one line
    item; persist + return the ClaimCheck. Does not commit — caller owns the transaction."""
    tool_input = LineItemInput(
        employee_id=item.employee_id,
        category=item.category,
        amount=item.amount,
        currency=item.currency,
        merchant=item.merchant,
        description=item.description,
        expense_date=item.expense_date,
        receipt_datetime=item.receipt_datetime,
        receipt_total=item.receipt_total,
        has_receipt=item.has_receipt,
    )

    policy_result = check_policy(tool_input, policy)
    category_result = classify_category(item.description, item.merchant)
    duplicate_result = detect_duplicates(
        CandidateLineItem(
            employee_id=item.employee_id,
            receipt_datetime=item.receipt_datetime,
            total=item.receipt_total or item.amount,
        ),
        _duplicate_history(session, item),
        near_match_days=policy.duplicate_near_match_days,
    )

    attachments = _attachments(session, item)
    scan_result = _scan_attachments(session, attachments)
    receipt_result = _reconcile_receipt(item, attachments, scan_result)

    check = ClaimCheck(
        line_item_id=item.id,
        sheet_version=_sheet_version(session, item),
        policy_result=policy_result.model_dump(mode="json"),
        category_result=category_result.model_dump(mode="json"),
        duplicate_result=duplicate_result.model_dump(mode="json"),
        receipt_result=receipt_result,
    )
    session.add(check)
    return check


def intake_hard_fails(check: ClaimCheck) -> bool:
    """True only for malware/infected receipts — the one thing a manager cannot safely resolve.
    Everything else (policy, reconciliation, duplicates) reaches the manager for human judgment.
    Never auto-returns the sheet to the employee for policy or data-quality reasons."""
    scan_status = ((check.receipt_result or {}).get("scan") or {}).get("status")
    return scan_status == ScanStatus.INFECTED.value


def intake_has_warnings(check: ClaimCheck) -> bool:
    """True when there are soft flags (policy, reconciliation, duplicates) that the manager
    should see, but that don't block the sheet from reaching them."""
    policy_ok = (check.policy_result or {}).get("status") == PolicyCheckStatus.PASS.value
    dup_risk = (check.duplicate_result or {}).get("risk")
    dup_ok = dup_risk not in ("high",)
    receipt = check.receipt_result or {}
    scan_ok = (receipt.get("scan") or {}).get("status") in (None, ScanStatus.CLEAN.value)
    reconcile_ok = (receipt.get("reconcile") or {}).get("status") != "fail"
    return not (policy_ok and dup_ok and scan_ok and reconcile_ok)


# Keep for backwards compatibility — now just an alias for not intake_hard_fails.
def intake_passes(check: ClaimCheck) -> bool:
    return not intake_hard_fails(check)


def intake_warning_reason(check: ClaimCheck) -> str:
    """Short human-readable summary of soft flags — shown to the manager, not the employee."""
    reasons = []
    policy_ok = (check.policy_result or {}).get("status") == PolicyCheckStatus.PASS.value
    if not policy_ok:
        clause = (check.policy_result or {}).get("clause_ref") or ""
        reasons.append(f"possible policy issue{' (' + clause + ')' if clause else ''}")
    dup_risk = (check.duplicate_result or {}).get("risk")
    if dup_risk == "high":
        reasons.append("exact duplicate detected")
    elif dup_risk == "medium":
        reasons.append("near-duplicate — check with employee")
    receipt = check.receipt_result or {}
    scan_status = (receipt.get("scan") or {}).get("status")
    if scan_status == ScanStatus.FAILED.value:
        reasons.append("receipt scan failed (inconclusive)")
    reconcile = receipt.get("reconcile") or {}
    if reconcile.get("status") == "fail":
        reasons.append(reconcile.get("detail") or "receipt line items don't sum to total")
    return "; ".join(reasons) if reasons else ""


# Legacy alias used in older call-sites.
def intake_fail_reason(check: ClaimCheck) -> str:
    return intake_warning_reason(check)


# --------------------------------------------------------------------------- #
# Malware scan (SCOPING §6.1 — fail-closed)
# --------------------------------------------------------------------------- #
def _scan_attachments(session: Session, attachments: list[Attachment]) -> dict:
    """Scan every attachment, persist its verdict, and summarise. Worst status wins:
    INFECTED/FAILED → the whole line item fails intake."""
    per_file: list[dict] = []
    worst = ScanStatus.CLEAN
    for att in attachments:
        verdict = malware_scan_service.scan_blob(att.blob_uri, settings)
        att.scan_status = verdict
        session.add(att)
        per_file.append({"attachment_id": att.id, "status": verdict.value})
        if verdict in (ScanStatus.INFECTED, ScanStatus.FAILED) and worst is ScanStatus.CLEAN:
            worst = verdict
    return {"status": worst.value, "attachments": per_file}


# --------------------------------------------------------------------------- #
# Receipt reconciliation (SCOPING §6.1 — Σ items + tax = total, tax sanity)
# --------------------------------------------------------------------------- #
def _reconcile_receipt(item: LineItem, attachments: list[Attachment], scan: dict) -> dict:
    """Reconcile the line item's receipt. Returns the persisted `receipt_result` dict with a
    `reconcile.status` of pass | fail | review, and sets `item.needs_human_review` when a
    receipt is unreadable or its total disagrees with the entered amount (Finance looks; the
    employee sees nothing). A definitive math failure is `fail` → returns to the employee."""
    reconcile = _reconcile_status(item, attachments, scan)
    if reconcile["status"] == "review":
        item.needs_human_review = True
        item.review_reason = reconcile.get("detail")
    else:
        # Reconciliation passed (or hard-failed) — clear any stale review flag so a fixed
        # amount that now matches the receipt no longer reads as needing Finance review.
        item.needs_human_review = False
        item.review_reason = None
    return {"scan": scan, "reconcile": reconcile}


def _reconcile_status(item: LineItem, attachments: list[Attachment], scan: dict) -> dict:
    # Don't OCR a receipt we already know is bad — a failed/infected scan fails intake anyway.
    if (scan.get("status") != ScanStatus.CLEAN.value) or not attachments:
        return {"status": "pass", "detail": None}

    out = receipt_scan_service.scan_receipt(attachments[-1].blob_uri, item.amount, settings)
    # Σ(items)+tax ≠ total with a positively-read total → hard data error (return to employee).
    if out.reconciles is False:
        return {
            "status": "fail",
            "reconciles": False,
            "delta": str(out.delta) if out.delta is not None else None,
            "detail": out.detail or "Receipt line items plus tax don't sum to the total.",
        }
    # Unreadable total or entered-amount mismatch → Finance reviews, sheet still proceeds.
    if out.human_intervention_required:
        return {
            "status": "review",
            "reconciles": out.reconciles,
            "matches_entered": out.matches_entered,
            "detail": out.detail,
        }
    return {
        "status": "pass",
        "reconciles": out.reconciles,
        "matches_entered": out.matches_entered,
        "delta": str(out.delta) if out.delta is not None else None,
        "detail": None,
    }


def _attachments(session: Session, item: LineItem) -> list[Attachment]:
    return list(
        session.exec(select(Attachment).where(Attachment.line_item_id == item.id)).all()
    )


def _sheet_version(session: Session, item: LineItem) -> int:
    from app.models.expense_sheet import ExpenseSheet  # noqa: PLC0415 — avoid import cycle

    sheet = session.get(ExpenseSheet, item.sheet_id)
    return sheet.version if sheet else 1


def _duplicate_history(session: Session, item: LineItem) -> list[HistoricalLineItem]:
    """Prior line items for the same employee — intra-sheet items are flagged via same_sheet."""
    rows = session.exec(
        select(LineItem).where(
            LineItem.employee_id == item.employee_id, LineItem.id != item.id
        )
    ).all()
    return [
        HistoricalLineItem(
            line_item_id=r.id,
            employee_id=r.employee_id,
            receipt_datetime=r.receipt_datetime,
            total=r.receipt_total or r.amount,
            same_sheet=(r.sheet_id == item.sheet_id),
        )
        for r in rows
    ]
