"""TripSense FastAPI REST API."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.api.agent import run_agent
from backend.database.db import get_db, init_db, row_to_dict, rows_to_dicts
from backend.mcp_server.policy_engine import load_policy
from backend.mcp_server.tools.receipt_tools import (
    classify_spend_category,
    detect_duplicate_claim,
    parse_receipt,
)
from backend.mcp_server.tools.report_tools import generate_trip_report, reconcile_trip
from backend.mcp_server.tools.trip_tools import (
    check_policy_compliance,
    plan_trip_budget,
    pre_approve_trip,
)

app = FastAPI(
    title="TripSense API",
    description="AI-powered business travel expense management",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


# --- Request models ---

class BudgetRequest(BaseModel):
    destination: str
    duration_days: int = Field(ge=1)
    purpose: str


class ComplianceRequest(BaseModel):
    trip_plan: dict[str, Any]
    employee_id: str


class PreApproveRequest(BaseModel):
    trip_plan: dict[str, Any]
    employee_id: str


class ReceiptParseRequest(BaseModel):
    image_path: str


class ClassifyRequest(BaseModel):
    merchant_name: str
    description: str = ""


class DuplicateRequest(BaseModel):
    employee_id: str
    merchant: str
    amount: float
    date: str


class ReconcileRequest(BaseModel):
    approval_token: str
    receipts: list[dict[str, Any]]


class ReportRequest(BaseModel):
    approval_token: str


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]


# --- Health ---

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tripsense"}


# --- Chat agent endpoint ---

@app.post("/api/chat")
def api_chat(req: ChatRequest) -> dict[str, Any]:
    """Drive Claude (claude-sonnet-4-6) over the 8 MCP tools for one user turn."""
    try:
        return run_agent(req.messages)
    except Exception as exc:
        # Most common cause: ANTHROPIC_API_KEY not set in the API server's env.
        raise HTTPException(status_code=502, detail=f"Chat agent error: {exc}") from exc


# --- MCP tool endpoints ---

@app.post("/api/budget/plan")
def api_plan_budget(req: BudgetRequest) -> dict[str, Any]:
    return plan_trip_budget(req.destination, req.duration_days, req.purpose)


@app.post("/api/policy/check")
def api_check_compliance(req: ComplianceRequest) -> dict[str, Any]:
    return check_policy_compliance(req.trip_plan, req.employee_id)


@app.post("/api/trip/pre-approve")
def api_pre_approve(req: PreApproveRequest) -> dict[str, Any]:
    return pre_approve_trip(req.trip_plan, req.employee_id)


@app.post("/api/receipt/parse")
def api_parse_receipt(req: ReceiptParseRequest) -> dict[str, Any]:
    return parse_receipt(req.image_path)


@app.post("/api/receipts/parse")
async def api_upload_receipt(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse an uploaded receipt image (jpg/png) and return normalized fields."""
    content_type = (file.content_type or "").lower()
    if content_type not in ("image/jpeg", "image/jpg", "image/png"):
        raise HTTPException(status_code=400, detail="Please upload a JPG or PNG image.")

    suffix = Path(file.filename or "").suffix or (".png" if "png" in content_type else ".jpg")
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        result = parse_receipt(tmp_path)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    # Normalize to the field names the chat UI expects.
    return {
        "merchant_name": result.get("merchant"),
        "merchant": result.get("merchant"),
        "date": result.get("date"),
        "total_amount": result.get("total") or result.get("amount"),
        "total": result.get("total") or result.get("amount"),
        "tax": result.get("tax"),
        "payment_method": result.get("payment_method"),
        "line_items": result.get("line_items", []),
        "reconciliation_flag": result.get("reconciliation_flag", False),
        "reconciliation_errors": result.get("reconciliation_errors", []),
        "ocr_confidence": result.get("ocr_confidence", 0.0),
        "error": result.get("error"),
    }


@app.post("/api/spend/classify")
def api_classify(req: ClassifyRequest) -> dict[str, Any]:
    return classify_spend_category(req.merchant_name, req.description)


@app.post("/api/claim/duplicate-check")
def api_duplicate_check(req: DuplicateRequest) -> dict[str, Any]:
    return detect_duplicate_claim(req.employee_id, req.merchant, req.amount, req.date)


@app.post("/api/trip/reconcile")
def api_reconcile(req: ReconcileRequest) -> dict[str, Any]:
    return reconcile_trip(req.approval_token, req.receipts)


@app.post("/api/trip/report")
def api_report(req: ReportRequest) -> dict[str, Any]:
    return generate_trip_report(req.approval_token)


# --- Data endpoints ---

@app.get("/api/employees")
def list_employees() -> list[dict[str, Any]]:
    with get_db() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM employees ORDER BY name").fetchall())


@app.get("/api/employees/{employee_id}")
def get_employee(employee_id: str) -> dict[str, Any]:
    with get_db() as conn:
        emp = row_to_dict(conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone())
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@app.get("/api/trips")
def list_trips() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trip_plans ORDER BY created_at DESC").fetchall()
        trips = rows_to_dicts(rows)
        for t in trips:
            t["budget_breakdown"] = json.loads(t["budget_breakdown"])
            if t.get("violations"):
                t["violations"] = json.loads(t["violations"])
    return trips


@app.get("/api/trips/{approval_token}")
def get_trip(approval_token: str) -> dict[str, Any]:
    with get_db() as conn:
        trip = row_to_dict(
            conn.execute("SELECT * FROM trip_plans WHERE approval_token = ?", (approval_token,)).fetchone()
        )
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip["budget_breakdown"] = json.loads(trip["budget_breakdown"])
    return trip


@app.get("/api/claims")
def list_claims(employee_id: str | None = None) -> list[dict[str, Any]]:
    with get_db() as conn:
        if employee_id:
            rows = conn.execute(
                "SELECT * FROM expense_claims WHERE employee_id = ? ORDER BY claim_date DESC",
                (employee_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM expense_claims ORDER BY claim_date DESC").fetchall()
    return rows_to_dicts(rows)


@app.get("/api/policy")
def get_policy() -> dict[str, Any]:
    policy_path = Path(__file__).resolve().parent.parent / "database" / "company_policy.json"
    with open(policy_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/dashboard/stats")
def dashboard_stats() -> dict[str, Any]:
    # A claim is a near-duplicate if another claim shares its employee, merchant,
    # and amount within ±3 days. Counting via this self-join includes BOTH members
    # of the pair (not just the one flagged with a high duplicate_risk score).
    dup_partner_exists = """
        EXISTS (
            SELECT 1 FROM expense_claims e2
            WHERE e2.id <> e.id
              AND e2.employee_id = e.employee_id
              AND LOWER(e2.merchant) = LOWER(e.merchant)
              AND ABS(e2.amount - e.amount) < 0.01
              AND ABS(julianday(e2.claim_date) - julianday(e.claim_date)) <= 3
        )
    """
    receipt_threshold = load_policy().get("receipt_required_above", 2000)

    with get_db() as conn:
        total_claims = conn.execute("SELECT COUNT(*) FROM expense_claims").fetchone()[0]
        violations = conn.execute(
            "SELECT COUNT(*) FROM expense_claims WHERE policy_violation = 1"
        ).fetchone()[0]
        duplicates = conn.execute(
            f"SELECT COUNT(*) FROM expense_claims e WHERE {dup_partner_exists}"
        ).fetchone()[0]
        missing_receipts = conn.execute(
            "SELECT COUNT(*) FROM expense_claims WHERE receipt_id IS NULL AND amount > ?",
            (receipt_threshold,),
        ).fetchone()[0]
        # Compliant = OK on every flag: no violation, not a duplicate, not missing a required receipt.
        compliant = conn.execute(
            f"""
            SELECT COUNT(*) FROM expense_claims e
            WHERE e.policy_violation = 0
              AND NOT (e.receipt_id IS NULL AND e.amount > ?)
              AND NOT {dup_partner_exists}
            """,
            (receipt_threshold,),
        ).fetchone()[0]
        total_spend = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expense_claims").fetchone()[0]
        total_at_risk = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) FROM expense_claims e
            WHERE policy_violation = 1
               OR duplicate_risk >= 0.7
               OR (receipt_id IS NULL AND amount > ?)
               OR {dup_partner_exists}
            """,
            (receipt_threshold,),
        ).fetchone()[0]
        trips = conn.execute("SELECT COUNT(*) FROM trip_plans").fetchone()[0]
    return {
        "total_claims": total_claims,
        "violations": violations,
        "duplicates": duplicates,
        "missing_receipts": missing_receipts,
        "compliant": compliant,
        "total_spend": round(total_spend, 2),
        "total_at_risk": round(total_at_risk, 2),
        "total_trips": trips,
    }
