from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db, Employee, AccountApproval, ExpenseClaim, ClaimError, DuplicateHistory, SystemAuditLedger
from backend.routers.auth import get_current_user
from backend.schemas import EmployeeRead
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/users", tags=["Users & Approvals"])

class ApprovalAction(BaseModel):
    action: str # "APPROVE" or "REJECT"

@router.get("/pending-approvals", response_model=list[EmployeeRead])
def get_pending_approvals(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns a list of users waiting for the current user's approval.
    Includes any user who has selected current_user as their manager.
    """
    role = current_user.role
    
    # 1. Direct reports: anyone who assigned this user as their manager
    direct_reports = db.query(Employee).filter(
        Employee.account_status == "PENDING_APPROVAL",
        Employee.manager_id == current_user.employee_id
    ).all()
    
    role_reports = []
    if role == "VP":
        # VPs approve Managers
        role_reports = db.query(Employee).filter(
            Employee.account_status == "PENDING_APPROVAL",
            Employee.role == "Manager"
        ).all()
        
    elif role in ["Director", "CEO"]:
        # Directors and CEOs approve VPs
        already_approved = db.query(AccountApproval.pending_employee_id).filter(
            AccountApproval.approver_id == current_user.employee_id
        )
        role_reports = db.query(Employee).filter(
            Employee.account_status == "PENDING_APPROVAL",
            Employee.role == "VP",
            ~Employee.employee_id.in_(already_approved)
        ).all()
        
    # Combine and de-duplicate by employee_id to avoid redundant listings
    combined = {emp.employee_id: emp for emp in (direct_reports + role_reports)}
    return list(combined.values())

@router.post("/{employee_id}/approve")
def approve_user(employee_id: str, action: ApprovalAction, current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    target_user = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if target_user.account_status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail="User is not pending approval")
        
    if action.action == "REJECT":
        target_user.account_status = "REJECTED"
        db.commit()
        return {"message": "User rejected"}
        
    # 1. Direct designated manager approval: if current user is the user's manager, approve immediately
    if target_user.manager_id == current_user.employee_id:
        target_user.account_status = "APPROVED"
        db.commit()
        return {"message": f"User {target_user.name} approved successfully by designated manager"}
        
    # 2. Hierarchy role-based fallback approvals
    if target_user.role in ["Software Engineer", "Analyst"]:
        if target_user.manager_id != current_user.employee_id:
            raise HTTPException(status_code=403, detail="You are not the designated manager for this user")
        target_user.account_status = "APPROVED"
        
    elif target_user.role == "Manager":
        if current_user.role != "VP":
            raise HTTPException(status_code=403, detail="Only VPs can approve Managers")
        target_user.account_status = "APPROVED"
        
    elif target_user.role == "VP":
        if current_user.role not in ["Director", "CEO"]:
            raise HTTPException(status_code=403, detail="Only Directors and CEOs can approve VPs")
            
        # Check if they already approved
        existing = db.query(AccountApproval).filter(
            AccountApproval.pending_employee_id == employee_id,
            AccountApproval.approver_id == current_user.employee_id
        ).first()
        if existing:
            return {"message": "You have already approved this user. Waiting for other signature."}
            
        # Record this approval
        new_approval = AccountApproval(
            pending_employee_id=employee_id,
            approver_id=current_user.employee_id,
            approver_role=current_user.role
        )
        db.add(new_approval)
        db.commit()
        
        # Check if both Director and CEO have approved
        approvals = db.query(AccountApproval).filter(AccountApproval.pending_employee_id == employee_id).all()
        roles_approved = set([a.approver_role for a in approvals])
        
        if "Director" in roles_approved and "CEO" in roles_approved:
            target_user.account_status = "APPROVED"
            db.commit()
            return {"message": "VP fully approved and account activated"}
        else:
            missing = "CEO" if "CEO" not in roles_approved else "Director"
            return {"message": f"Approval recorded. Still waiting for {missing} approval."}
    
    db.commit()
    return {"message": f"User {target_user.name} approved successfully"}


# ── CEO: Active Organisation Users ──────────────────────────────────────────

@router.get("/active")
def get_active_users(
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CEO-only: Returns all active employees with manager info and expense stats.
    """
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Only the CEO can view the full organisation list.")

    employees = db.query(Employee).filter(Employee.account_status == "APPROVED").all()

    result = []
    for emp in employees:
        # Get manager name
        manager_name = None
        if emp.manager_id:
            mgr = db.query(Employee).filter(Employee.employee_id == emp.manager_id).first()
            manager_name = mgr.name if mgr else None

        # Total expenses
        total_exp = db.query(func.sum(ExpenseClaim.amount)).filter(
            ExpenseClaim.employee_id == emp.employee_id
        ).scalar() or 0.0

        exp_count = db.query(func.count(ExpenseClaim.claim_id)).filter(
            ExpenseClaim.employee_id == emp.employee_id
        ).scalar() or 0

        # Earliest claim as a proxy for "join" activity (no created_at field on Employee)
        first_claim = db.query(ExpenseClaim.submission_timestamp).filter(
            ExpenseClaim.employee_id == emp.employee_id
        ).order_by(ExpenseClaim.submission_timestamp.asc()).first()

        result.append({
            "employee_id": emp.employee_id,
            "name": emp.name,
            "email": emp.email or "—",
            "role": emp.role,
            "department": emp.department,
            "account_status": emp.account_status,
            "manager_id": emp.manager_id,
            "manager_name": manager_name or ("CEO (Self)" if emp.role == "CEO" else "No Manager"),
            "total_expenses": round(float(total_exp), 2),
            "expense_count": exp_count,
            "first_activity": first_claim[0].isoformat() if first_claim and first_claim[0] else None,
        })

    return result


@router.delete("/{employee_id}")
def delete_user(
    employee_id: str,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CEO-only: Hard-deletes an employee account and all associated data.
    """
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Only the CEO can delete accounts.")

    if employee_id == current_user.employee_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    target = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found.")

    # Clean up related records
    claims = db.query(ExpenseClaim).filter(ExpenseClaim.employee_id == employee_id).all()
    for claim in claims:
        db.query(ClaimError).filter(ClaimError.claim_id == claim.claim_id).delete(synchronize_session=False)
        db.query(DuplicateHistory).filter(
            (DuplicateHistory.original_claim_id == claim.claim_id) |
            (DuplicateHistory.duplicate_claim_id == claim.claim_id)
        ).delete(synchronize_session=False)

    db.query(ExpenseClaim).filter(ExpenseClaim.employee_id == employee_id).delete(synchronize_session=False)
    db.query(SystemAuditLedger).filter(SystemAuditLedger.actor_id == employee_id).delete(synchronize_session=False)
    db.query(AccountApproval).filter(
        (AccountApproval.pending_employee_id == employee_id) |
        (AccountApproval.approver_id == employee_id)
    ).delete(synchronize_session=False)
    db.query(Employee).filter(Employee.employee_id == employee_id).delete(synchronize_session=False)
    db.commit()

    return {"message": f"Employee {target.name} and all associated data deleted successfully."}
