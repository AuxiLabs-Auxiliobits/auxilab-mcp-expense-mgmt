"""
ExpenseOps Expenses Router
==========================
Handles all expense claim submissions, receipt image uploads with OCR parsing,
manual audits (approvals/rejections/escalations), and bulk importing.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db, Employee, ExpenseClaim, ClaimError, SystemAuditLedger, DuplicateHistory
from backend.schemas import ExpenseClaimCreate, ExpenseClaimRead, ExpenseClaimUpdate, OCRExtractedReceipt, PaginatedExpenses
from backend.engines import PolicyEngine, RiskEngine, DuplicateEngine, ExpenseContext
from backend.exceptions_engine import ExceptionEngine
from backend.ai_layer import perform_ocr, parse_receipt_text, classify_expense, parse_receipt_with_vision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["Expenses"])

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from backend.routers.auth import get_current_user

@router.get("/", response_model=PaginatedExpenses)
def list_expenses(
    employee_id: Optional[str] = Query(None, description="Filter by employee"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_amount: Optional[float] = Query(None, description="Filter by minimum amount"),
    max_amount: Optional[float] = Query(None, description="Filter by maximum amount"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Retrieves list of expense claims, with advanced query filtering and sorting
    by submission timestamp. Enforces RBAC visibility rules.
    """
    query = db.query(ExpenseClaim)
    
    # Enforce Role-Based Visibility
    if current_user.role in ["Software Engineer", "Analyst"]:
        query = query.filter(ExpenseClaim.employee_id == current_user.employee_id)
    elif current_user.role == "Manager":
        managed_employee_ids = db.query(Employee.employee_id).filter(
            Employee.manager_id == current_user.employee_id,
            Employee.role != "Manager"
        )
        query = query.filter(
            (ExpenseClaim.employee_id == current_user.employee_id) | 
            (ExpenseClaim.employee_id.in_(managed_employee_ids))
        )
    # Executive roles (Director, VP, CEO) can view all expenses.
    
    if employee_id:
        query = query.filter(ExpenseClaim.employee_id == employee_id)
    if status_filter:
        query = query.filter(ExpenseClaim.status == status_filter)
    if category:
        query = query.filter(ExpenseClaim.category == category)
    if min_amount is not None:
        query = query.filter(ExpenseClaim.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(ExpenseClaim.amount <= max_amount)
        
    # Pagination
    total = query.count()
    items = query.order_by(ExpenseClaim.submission_timestamp.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/summary", response_model=dict[str, str])
def get_employee_summary(
    employee_id: str,
    start_date: str,
    end_date: str,
    current_user: Employee = Depends(get_current_user)
):
    """
    Generates an AI-driven executive summary of an employee's expense claims 
    over a specified period. Only available to Managers and Executives.
    """
    if current_user.role in ["Software Engineer", "Analyst"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only Managers and above can generate employee summaries."
        )
        
    from backend.mcp_tools import summarise_expense_report
    
    try:
        report = summarise_expense_report(employee_id, start_date, end_date)
        return {"report": report}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.get("/{claim_id}", response_model=ExpenseClaimRead)
def get_expense(claim_id: str, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """
    Retrieves a single claim by its unique ID. Enforces RBAC visibility.
    """
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense claim '{claim_id}' not found.",
        )
    
    # RBAC: employees can only see their own claims
    if current_user.role in ["Software Engineer", "Analyst"]:
        if claim.employee_id != current_user.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this claim.")
    elif current_user.role == "Manager":
        managed_ids = [e.employee_id for e in db.query(Employee).filter(Employee.manager_id == current_user.employee_id).all()]
        if claim.employee_id != current_user.employee_id and claim.employee_id not in managed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this claim.")
    # Executives (Director, VP, CEO) can view all
    
    return claim


@router.delete("/clear", status_code=status.HTTP_200_OK)
def clear_all_expenses(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """
    Development/Utility endpoint to clear all expenses and related audit logs.
    Restricted to CEO only.
    """
    if current_user.role != "CEO":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the CEO can perform a full data clear.")
    try:
        db.query(ClaimError).delete()
        db.query(DuplicateHistory).delete()
        db.query(SystemAuditLedger).delete()
        db.query(ExpenseClaim).delete()
        db.commit()
        return {"status": "success", "detail": "All expense data cleared."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear data: {str(e)}"
        )


@router.post("/submit", response_model=ExpenseClaimRead, status_code=status.HTTP_201_CREATED)
def submit_expense(payload: ExpenseClaimCreate, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """
    Core Pipeline Endpoint:
    Submits a claim through the multi-tier deterministic validation engines.
    1. Checks if employee exists, gets their role/department.
    2. Runs PolicyEngine for standard checks.
    3. Runs DuplicateEngine for double-submission check.
    4. Runs RiskEngine to compute a composite risk score.
    5. Runs ExceptionEngine if policy or duplicate failures occur to handle routing.
    6. Saves the claim, inserts errors, and writes to system audit ledger.
    """
    if payload.employee_id != current_user.employee_id:
        # Allow managers and above to submit on behalf of others, provided they manage them
        if current_user.role in ["Software Engineer", "Analyst"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only submit expenses for yourself."
            )
        elif current_user.role == "Manager":
            managed_ids = [e.employee_id for e in db.query(Employee).filter(Employee.manager_id == current_user.employee_id).all()]
            if payload.employee_id not in managed_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only submit expenses for your team.")
        # Execs can submit for anyone

    # 1. Employee lookup
    employee = db.query(Employee).filter(Employee.employee_id == payload.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Employee '{payload.employee_id}' does not exist. Cannot submit claim.",
        )

    # Prepare standardized context object for engines
    context = ExpenseContext(
        amount=float(payload.amount),
        category=payload.category,
        merchant_name=payload.merchant_name,
        transaction_date=payload.transaction_date,
        employee_role=employee.role,
        employee_id=employee.employee_id,
        receipt_path=payload.receipt_path,
        submission_hour=datetime.now().hour,
        location="NY_HQ", # Default location to NY_HQ for demo
    )

    # Initialize Engines
    policy_engine = PolicyEngine(db)
    duplicate_engine = DuplicateEngine(db)
    risk_engine = RiskEngine(db)
    # Note: ExceptionEngine is not invoked during submission.
    # REJECTED / ESCALATED are only set by the /review endpoint (manual authority action).

    # 2. Run Duplicate Check
    dup_res = duplicate_engine.evaluate(context)

    # 3. Run Policy Validation
    policy_res = policy_engine.evaluate(context)

    # 4. Run Risk Engine
    risk_res = risk_engine.evaluate(context, policy_result=policy_res, duplicate_result=dup_res)

    # ── CEO Fast-Path: always auto-approved, no engine processing needed ──
    if employee.role == "CEO":
        notes_list = []
        if hasattr(payload, "user_remarks") and payload.user_remarks:
            notes_list.append(f"User Remarks: {payload.user_remarks}")
        notes_list.append(f"CEO Auto-Approved | Composite Risk: {risk_res.score} ({risk_res.level})")
        system_notes = " | ".join(notes_list)

        new_claim = ExpenseClaim(
            claim_id=f"CLM-{uuid.uuid4().hex[:8].upper()}",
            employee_id=payload.employee_id,
            amount=payload.amount,
            currency=payload.currency,
            category=payload.category,
            merchant_name=payload.merchant_name,
            transaction_date=payload.transaction_date,
            submission_timestamp=datetime.utcnow(),
            status="APPROVED",
            risk_score=risk_res.score,
            receipt_path=payload.receipt_path,
            system_notes=system_notes,
            ai_summary=None,
        )
        db.add(new_claim)
        db.flush()

        audit = SystemAuditLedger(
            actor_id="SYSTEM",
            action_type="SUBMIT_EXPENSE",
            target_resource=f"expense_claims/{new_claim.claim_id}",
            before_state_json=None,
            after_state_json=json.dumps({
                "claim_id": new_claim.claim_id,
                "employee_id": new_claim.employee_id,
                "amount": float(new_claim.amount),
                "status": new_claim.status,
                "risk_score": float(new_claim.risk_score),
                "violations": [],
            }),
        )
        db.add(audit)
        db.commit()
        db.refresh(new_claim)
        return new_claim

    # ── Non-CEO Status Determination ────────────────────────────────────────
    # Rule 1: If user has added a comment (user_remarks) → Exception (pending review)
    # Rule 2: No comment + amount > $350 → Pending
    # Rule 3: No comment + amount ≤ $350 → Approved
    # Note:  REJECTED and ESCALATED can ONLY be set by a high-authority manual review
    #        (via the /review endpoint). The submit pipeline never sets those states.

    has_comment = bool(getattr(payload, "user_remarks", None))
    system_status = "APPROVED"
    violated_rules = []
    escalation_notes = ""

    # Read auto-approval threshold from policy_rules.json (single source of truth)
    # This avoids the need for AUTO_APPROVAL_THRESHOLD in .env
    import json as _json
    from backend.config import get_settings as _get_settings
    _settings = _get_settings()
    try:
        with open(_settings.POLICY_FILE_PATH, "r") as _pf:
            _policy_data = _json.load(_pf)
        threshold = float(_policy_data.get("global_rules", {}).get("auto_approval_threshold", 350.0))
    except Exception:
        threshold = 350.0  # Safe fallback

    if has_comment:
        # Any comment triggers an exception hold for manual review
        system_status = "EXCEPTION_HOLD"
        escalation_notes = "Exception flagged: User remarks present – routed to manager for review."
    elif float(payload.amount) > threshold:
        # No comment but amount exceeds threshold → pending approval
        system_status = "PENDING"
        escalation_notes = f"Amount ${float(payload.amount):.2f} exceeds ${threshold:.2f} threshold – pending manager approval."
    else:
        # No comment, within threshold → auto-approved
        system_status = "APPROVED"

    # Also collect violations from engines for audit trail notes
    # (these do NOT override the status rules above)
    if policy_res.status == "EXCEPTION" or dup_res.is_duplicate or risk_res.level == "HIGH":
        if dup_res.is_duplicate:
            violated_rules.append("RULE_DUPLICATE_SUBMISSION")
        violated_rules.extend(policy_res.failed_rules)
        # Remove duplicates
        violated_rules = list(dict.fromkeys(violated_rules))

    # Construct clean system notes narrative
    notes_list = []
    if has_comment:
        notes_list.append(f"User Remarks: {payload.user_remarks}")
    if violated_rules:
        notes_list.append(f"Violations: {', '.join(violated_rules)}")
    if escalation_notes:
        notes_list.append(escalation_notes)
    notes_list.append(f"Composite Risk: {risk_res.score} ({risk_res.level})")
    system_notes = " | ".join(notes_list)

    ai_summary = None
    if system_status != "APPROVED":
        from backend.ai_layer import generate_claim_narrative
        from backend.config import get_settings
        api_key = get_settings().XAI_API_KEY
        expense_data = {
            "category": payload.category,
            "amount": payload.amount,
            "merchant_name": payload.merchant_name,
        }
        ai_summary = generate_claim_narrative(
            expense_data=expense_data,
            violated_rules=violated_rules,
            risk_level=risk_res.level,
            is_duplicate=dup_res.is_duplicate,
            api_key=api_key
        )

    # 6. Insert new claim
    new_claim = ExpenseClaim(
        claim_id=f"CLM-{uuid.uuid4().hex[:8].upper()}",
        employee_id=payload.employee_id,
        amount=payload.amount,
        currency=payload.currency,
        category=payload.category,
        merchant_name=payload.merchant_name,
        transaction_date=payload.transaction_date,
        submission_timestamp=datetime.utcnow(),
        status=system_status,
        risk_score=risk_res.score,
        receipt_path=payload.receipt_path,
        system_notes=system_notes,
        ai_summary=ai_summary,
    )
    db.add(new_claim)
    db.flush()  # populate new_claim.claim_id

    # Save claim errors
    for rule in violated_rules:
        db.add(ClaimError(claim_id=new_claim.claim_id, rule_violated=rule))

    # 7. Write to System Audit Ledger (Immutable logging)
    audit = SystemAuditLedger(
        actor_id="SYSTEM",
        action_type="SUBMIT_EXPENSE",
        target_resource=f"expense_claims/{new_claim.claim_id}",
        before_state_json=None,
        after_state_json=json.dumps({
            "claim_id": new_claim.claim_id,
            "employee_id": new_claim.employee_id,
            "amount": float(new_claim.amount),
            "status": new_claim.status,
            "risk_score": float(new_claim.risk_score),
            "violations": violated_rules,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(new_claim)

    return new_claim


@router.put("/{claim_id}/review", response_model=ExpenseClaimRead)
def review_expense(
    claim_id: str,
    payload: ExpenseClaimUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Enables finance auditors or managers to manual override, approve,
    or reject a pending/escalated claim. Appends system audit records.
    """
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense claim '{claim_id}' not found.",
        )

    if claim.employee_id == current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot review your own expense claim."
        )

    claim_owner = db.query(Employee).filter(Employee.employee_id == claim.employee_id).first()
    if claim_owner:
        if claim_owner.role == "Manager":
            if current_user.role not in ["VP", "Director", "CEO"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Manager claims can only be reviewed by a VP, Director, or CEO."
                )
        elif claim_owner.role == "VP":
            if current_user.role not in ["Director", "CEO"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="VP claims can only be reviewed by a Director or CEO."
                )

    before_state = {
        "claim_id": claim.claim_id,
        "status": claim.status,
        "amount": float(claim.amount),
        "system_notes": claim.system_notes,
    }

    # Apply updates
    if payload.status:
        if payload.status not in ["APPROVED", "REJECTED", "EXCEPTION_HOLD", "ESCALATED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid review status: '{payload.status}'",
            )
        claim.status = payload.status

    # Allow reviewer to correct / adjust the expense amount
    if payload.amount is not None and payload.amount > 0:
        claim.amount = payload.amount

    if payload.system_notes:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        reviewer_name = current_user.name if hasattr(current_user, "name") else current_user.employee_id
        new_note = f"[{timestamp} Reviewer: {reviewer_name}] {payload.system_notes}"
        claim.system_notes = f"{claim.system_notes} | {new_note}" if claim.system_notes else new_note

    if payload.risk_score is not None:
        claim.risk_score = payload.risk_score

    # Immutable Audit Log
    audit = SystemAuditLedger(
        actor_id=current_user.employee_id,
        action_type="REVIEW_EXPENSE",
        target_resource=f"expense_claims/{claim.claim_id}",
        before_state_json=json.dumps(before_state),
        after_state_json=json.dumps({
            "claim_id": claim.claim_id,
            "status": claim.status,
            "amount": float(claim.amount),
            "system_notes": claim.system_notes,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(claim)

    return claim


@router.post("/upload-receipt", response_model=OCRExtractedReceipt)
def upload_receipt(file: UploadFile = File(...), current_user: Employee = Depends(get_current_user)):
    """
    Handles receipt image uploads.
    1. Saves file to data/uploads/.
    2. Runs pytesseract OCR to extract raw text.
    3. Runs AI Layer receipt text parser (regex/LLM) to extract structured fields.
    4. Returns OCRExtractedReceipt.
    """
    # Validate MIME type
    if not file.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload an image or PDF.",
        )

    # Save to disk
    file_ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    dest_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        parsed = None
        is_image = file.content_type.startswith("image/")
        
        # === PRIMARY: Vision LLM (for image files) ===
        # Sends the raw image to Llama 4 Scout which "looks" at it directly.
        # This handles blurry, faint, shadowy, and thermal receipts perfectly.
        if is_image:
            logger.info(f"Attempting Vision LLM parsing for {file.filename}")
            parsed = parse_receipt_with_vision(dest_path)
            if parsed:
                logger.info(f"Vision LLM succeeded: merchant={parsed.merchant}, total={parsed.total_amount}")
        
        # === FALLBACK: OCR + Text LLM (for PDFs or if vision fails) ===
        if not parsed:
            logger.info(f"Falling back to OCR + Text LLM pipeline for {file.filename}")
            ocr_text = perform_ocr(dest_path, original_filename=file.filename)
            parsed = parse_receipt_text(ocr_text)
        
        # Inject file path into response
        parsed.receipt_path = f"uploads/{unique_filename}"
        return parsed
    except Exception as exc:
        logger.error(f"Receipt OCR pipeline crashed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR Extraction failed: {str(exc)}",
        )


@router.get("/uploads/{filename}")
def get_receipt_file(filename: str, current_user: Employee = Depends(get_current_user)):
    """
    Secure endpoint to retrieve uploaded receipt files.
    """
    # Prevent directory traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename.")
        
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")
        
    return FileResponse(file_path)

@router.post("/bulk-import", response_model=dict[str, Any])
def bulk_import(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    if current_user.role in ["Software Engineer", "Analyst"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Managers and above can perform bulk imports.")
    """
    Processes bulk importing of claims via CSV or JSON formats.
    Evaluates each claim in the batch, saving them and listing passes/failures.
    """
    import csv
    import io

    filename = file.filename.lower()
    imported_count = 0
    errors = []

    try:
        content = file.file.read().decode("utf-8")
        claims_to_process = []

        if filename.endswith(".json"):
            claims_to_process = json.loads(content)
        elif filename.endswith(".csv"):
            f = io.StringIO(content)
            reader = csv.DictReader(f)
            for row in reader:
                claims_to_process.append(row)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid bulk import file type. Supports CSV or JSON.",
            )

        for idx, row in enumerate(claims_to_process):
            try:
                # Convert string fields
                emp_id = row.get("employee_id")
                amount = float(row.get("amount", 0))
                category = row.get("category")
                merchant = row.get("merchant_name")
                
                # Try parsing transaction date
                date_str = row.get("transaction_date")
                txn_date = date.fromisoformat(date_str) if date_str else date.today()

                # Call standard submit process
                create_payload = ExpenseClaimCreate(
                    employee_id=emp_id,
                    amount=amount,
                    currency=row.get("currency", "USD"),
                    category=category,
                    merchant_name=merchant,
                    transaction_date=txn_date,
                    receipt_path=row.get("receipt_path"),
                )
                submit_expense(create_payload, db, current_user=current_user)
                imported_count += 1
            except Exception as e:
                errors.append(f"Row {idx+1} failed: {str(e)}")

        return {
            "status": "success",
            "imported_count": imported_count,
            "failed_count": len(errors),
            "errors": errors,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk import process failed: {str(exc)}"
        )
