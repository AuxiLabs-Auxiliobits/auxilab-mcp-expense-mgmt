"""
ExpenseOps Dashboard Router
===========================
Generates top-level KPI metrics, structured chart data, and CSV/JSON reporting
aggregations for the frontend dashboard.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db, Employee, ExpenseClaim, ClaimError, DuplicateHistory
from backend.schemas import DashboardMetrics, ChartData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from backend.routers.auth import get_current_user

@router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Computes top-level KPIs from database tables.
    Applies RBAC so Managers only see metrics for their team.
    """
    query = db.query(ExpenseClaim)
    
    if current_user.role == "Manager":
        managed_ids = db.query(Employee.employee_id).filter(Employee.manager_id == current_user.employee_id)
        query = query.filter(
            (ExpenseClaim.employee_id == current_user.employee_id) | 
            (ExpenseClaim.employee_id.in_(managed_ids))
        )

    total_expenses = query.count()
    if total_expenses == 0:
        return DashboardMetrics(
            total_expenses=0,
            total_amount=0.0,
            compliance_rate=100.0,
            auto_pass_rate=100.0,
            pending_count=0,
            high_risk_count=0,
            duplicate_count=0,
            avg_risk_score=0.0,
        )

    # Base query for sums and averages to reuse the filters
    base_claims = query.subquery()

    total_amount = float(
        db.query(func.sum(base_claims.c.amount))
        .filter(base_claims.c.status != "REJECTED")
        .scalar() or 0.0
    )

    # Compliance Rate
    claims_with_errors = db.query(ClaimError.claim_id).join(base_claims, ClaimError.claim_id == base_claims.c.claim_id).distinct().count()
    compliant_claims = total_expenses - claims_with_errors
    compliance_rate = (compliant_claims / total_expenses) * 100.0

    # Auto-pass rate
    approved_claims = db.query(base_claims).filter(base_claims.c.status == "APPROVED").count()
    auto_pass_rate = (approved_claims / total_expenses) * 100.0

    # Counts
    pending_count = db.query(base_claims).filter(base_claims.c.status == "PENDING").count()
    high_risk_count = db.query(base_claims).filter(base_claims.c.risk_score >= 70.0).count()
    
    # Duplicate Count
    if current_user.role == "Manager":
        duplicate_count = db.query(DuplicateHistory).join(ExpenseClaim, DuplicateHistory.duplicate_claim_id == ExpenseClaim.claim_id).filter(
            (ExpenseClaim.employee_id == current_user.employee_id) | 
            (ExpenseClaim.employee_id.in_(db.query(Employee.employee_id).filter(Employee.manager_id == current_user.employee_id)))
        ).count()
    else:
        duplicate_count = db.query(DuplicateHistory).count()
    
    # Average Risk Score
    avg_risk = float(db.query(func.avg(base_claims.c.risk_score)).scalar() or 0.0)

    return DashboardMetrics(
        total_expenses=total_expenses,
        total_amount=round(total_amount, 2),
        compliance_rate=round(compliance_rate, 2),
        auto_pass_rate=round(auto_pass_rate, 2),
        pending_count=pending_count,
        high_risk_count=high_risk_count,
        duplicate_count=duplicate_count,
        avg_risk_score=round(avg_risk, 2),
    )


@router.get("/charts", response_model=ChartData)
def get_chart_data(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Groups database columns into formatted chart payload data arrays.
    Applies RBAC so Managers only see charts for their team.
    """
    query = db.query(ExpenseClaim)
    
    if current_user.role == "Manager":
        managed_ids = db.query(Employee.employee_id).filter(Employee.manager_id == current_user.employee_id)
        query = query.filter(
            (ExpenseClaim.employee_id == current_user.employee_id) | 
            (ExpenseClaim.employee_id.in_(managed_ids))
        )
    
    base_claims = query.subquery()

    # 1. Spend by Category
    category_spend = (
        db.query(base_claims.c.category, func.sum(base_claims.c.amount))
        .filter(base_claims.c.status != "REJECTED")
        .group_by(base_claims.c.category)
        .all()
    )
    spend_by_cat = {cat: float(spend) for cat, spend in category_spend}

    # 2. Risk Distribution Buckets
    low_risk = db.query(base_claims).filter(base_claims.c.risk_score < 35.0).count()
    med_risk = db.query(base_claims).filter(
        base_claims.c.risk_score >= 35.0,
        base_claims.c.risk_score < 70.0,
    ).count()
    high_risk = db.query(base_claims).filter(base_claims.c.risk_score >= 70.0).count()
    
    risk_dist = [
        {"bucket": "Low (0-35)", "count": low_risk},
        {"bucket": "Medium (36-70)", "count": med_risk},
        {"bucket": "High (71-100)", "count": high_risk},
    ]

    # 3. Monthly Trend
    # For SQLite, group by strftime('%m', transaction_date), otherwise simple fallback
    trend_query = (
        db.query(
            func.strftime("%Y-%m", base_claims.c.transaction_date).label("month"),
            func.sum(base_claims.c.amount).label("total"),
        )
        .filter(base_claims.c.status != "REJECTED")
        .group_by("month")
        .order_by("month")
        .all()
    )
    monthly_trend = [{"month": m, "amount": float(t)} for m, t in trend_query]
    if not monthly_trend:
        monthly_trend = [{"month": date.today().strftime("%Y-%m"), "amount": 0.0}]

    # 4. Approval Status
    status_counts = (
        db.query(base_claims.c.status, func.count(base_claims.c.claim_id))
        .group_by(base_claims.c.status)
        .all()
    )
    approval_status = {stat: count for stat, count in status_counts}

    # 5. Violations by Employee
    violations = (
        db.query(Employee.name, func.count(ClaimError.error_id))
        .join(base_claims, Employee.employee_id == base_claims.c.employee_id)
        .join(ClaimError, base_claims.c.claim_id == ClaimError.claim_id)
        .group_by(Employee.name)
        .all()
    )
    violations_by_emp = {name: count for name, count in violations}

    return ChartData(
        spend_by_category=spend_by_cat,
        risk_distribution=risk_dist,
        monthly_trend=monthly_trend,
        approval_status=approval_status,
        violations_by_employee=violations_by_emp,
    )


@router.get("/export")
def export_claims_csv(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """
    Exports the audit ledger / expense list as a CSV download.
    Applies RBAC so Managers only export their team's data.
    """
    query = db.query(ExpenseClaim)
    
    if current_user.role == "Manager":
        managed_ids = db.query(Employee.employee_id).filter(Employee.manager_id == current_user.employee_id)
        query = query.filter(
            (ExpenseClaim.employee_id == current_user.employee_id) | 
            (ExpenseClaim.employee_id.in_(managed_ids))
        )
    
    claims = query.order_by(ExpenseClaim.submission_timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header Row
    writer.writerow([
        "Claim ID", "Employee ID", "Amount", "Currency", "Category", 
        "Merchant Name", "Transaction Date", "Submission Time", "Status", "Risk Score", "System Notes"
    ])
    
    # Data Rows
    for claim in claims:
        writer.writerow([
            claim.claim_id,
            claim.employee_id,
            float(claim.amount),
            claim.currency,
            claim.category,
            claim.merchant_name,
            claim.transaction_date.isoformat(),
            claim.submission_timestamp.isoformat() if claim.submission_timestamp else "",
            claim.status,
            float(claim.risk_score),
            claim.system_notes or ""
        ])
        
    output.seek(0)
    
    headers = {
        "Content-Disposition": "attachment; filename=expense_audit_report.csv"
    }
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers=headers
    )
