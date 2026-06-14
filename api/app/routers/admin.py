"""Admin routes (SCOPING §3.1, §7). Onboard/soft-delete agencies, manage users & roles.

Agency delete is a SOFT delete and is blocked while open sheets reference it (SCOPING §8
referential integrity)."""

from __future__ import annotations

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import require
from app.db import get_session
from app.models.agency import Agency, AgencyStatus
from app.models.expense_sheet import ExpenseSheet
from app.models.user import User
from app.principal import Principal, Role
from app.rbac.permissions import Capability
from app.schemas.dto import AgencyCreate, AgencyUpdate, UserCreate, UserOut, UserUpdate
from app.services import audit_service
from expense_core.schemas.enums import SheetStatus

router = APIRouter(prefix="/admin", tags=["admin"])
_ph = PasswordHasher()

_OPEN_STATES = {
    SheetStatus.SUBMITTED, SheetStatus.IN_MANAGER_REVIEW, SheetStatus.IN_FINANCE_REVIEW,
    SheetStatus.FINANCE_MANUAL_REVIEW, SheetStatus.RETURNED_TO_EMPLOYEE,
}


def _parse_role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid role '{value}'; expected one of {[r.value for r in Role]}",
        ) from e


@router.get("/agencies", response_model=list[Agency])
async def list_agencies(
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> list[Agency]:
    return list(session.exec(select(Agency)).all())


@router.post("/agencies", response_model=Agency, status_code=status.HTTP_201_CREATED)
async def create_agency(
    body: AgencyCreate,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> Agency:
    agency = Agency(name=body.name, created_by=principal.subject_id)
    session.add(agency)
    audit_service.record(session, actor=principal, action="AGENCY_ONBOARDED",
                         entity=f"agency:{agency.id}", after={"name": body.name})
    session.commit()
    session.refresh(agency)
    return agency


@router.get("/agencies/{agency_id}", response_model=Agency)
async def get_agency(
    agency_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> Agency:
    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="agency not found")
    return agency


@router.patch("/agencies/{agency_id}", response_model=Agency)
async def update_agency(
    agency_id: str,
    body: AgencyUpdate,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> Agency:
    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="agency not found")

    before = {"name": agency.name, "status": agency.status}
    if body.name is not None:
        clash = session.exec(
            select(Agency).where(Agency.name == body.name, Agency.id != agency_id)
        ).first()
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="agency name already exists")
        agency.name = body.name
    if body.status is not None:
        try:
            agency.status = AgencyStatus(body.status)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid status; expected one of {[s.value for s in AgencyStatus]}",
            ) from e

    session.add(agency)
    audit_service.record(session, actor=principal, action="AGENCY_UPDATED",
                         entity=f"agency:{agency.id}", before=before,
                         after={"name": agency.name, "status": agency.status})
    session.commit()
    session.refresh(agency)
    return agency


@router.delete("/agencies/{agency_id}", response_model=Agency)
async def soft_delete_agency(
    agency_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> Agency:
    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="agency not found")

    open_count = len(
        session.exec(
            select(ExpenseSheet).where(
                ExpenseSheet.agency_id == agency_id,
                ExpenseSheet.status.in_(_OPEN_STATES),  # type: ignore[attr-defined]
            )
        ).all()
    )
    if open_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"cannot delete agency with {open_count} open sheet(s)",
        )

    agency.status = AgencyStatus.SOFT_DELETED
    session.add(agency)
    audit_service.record(session, actor=principal, action="AGENCY_SOFT_DELETED",
                         entity=f"agency:{agency.id}")
    session.commit()
    session.refresh(agency)
    return agency


@router.get("/users", response_model=list[UserOut])
async def list_users(
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
    agency_id: str | None = None,
    is_active: bool | None = None,
) -> list[User]:
    """List all users, optionally filtered by agency and active state."""
    stmt = select(User)
    if agency_id is not None:
        stmt = stmt.where(User.agency_id == agency_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    return list(session.exec(stmt).all())


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    if session.exec(select(User).where(User.email == body.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="email already exists")

    user = User(
        name=body.name, email=body.email, role=_parse_role(body.role), agency_id=body.agency_id,
        password_hash=_ph.hash(body.password) if body.password else None,
    )
    session.add(user)
    audit_service.record(session, actor=principal, action="USER_CREATED",
                         entity=f"user:{user.id}", after={"email": body.email, "role": body.role})
    session.commit()
    session.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UserUpdate,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    """Partial update. Only provided fields change; `password` is re-hashed if present."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")

    before = {"email": user.email, "role": user.role, "agency_id": user.agency_id,
              "is_active": user.is_active}

    if body.email is not None and body.email != user.email:
        clash = session.exec(
            select(User).where(User.email == body.email, User.id != user_id)
        ).first()
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="email already exists")
        user.email = body.email
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = _parse_role(body.role)
    if body.agency_id is not None:
        user.agency_id = body.agency_id
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.password_hash = _ph.hash(body.password)

    session.add(user)
    audit_service.record(session, actor=principal, action="USER_UPDATED",
                         entity=f"user:{user.id}", before=before,
                         after={"email": user.email, "role": user.role,
                                "agency_id": user.agency_id, "is_active": user.is_active})
    session.commit()
    session.refresh(user)
    return user


@router.delete("/users/{user_id}", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    """Soft delete: deactivate the account. Users are never hard-deleted because sheets,
    decisions, and the audit log reference them (SCOPING §8). Re-enable via PATCH is_active."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.id == principal.subject_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="cannot deactivate your own account")

    user.is_active = False
    session.add(user)
    audit_service.record(session, actor=principal, action="USER_DEACTIVATED",
                         entity=f"user:{user.id}")
    session.commit()
    session.refresh(user)
    return user
