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
from app.schemas.dto import (
    AgencyCreate,
    AgencyOut,
    AgencyUpdate,
    AssignRoleRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.config import settings
from app.serializers import agencies_to_out, agency_to_out
from app.services import audit_service, escalation_service
from app.services import password_reset_service as prs
from expense_core.schemas.enums import SheetStatus

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Admin role required"},
    },
)
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


@router.get("/agencies", response_model=list[AgencyOut], summary="List agencies (with user counts)")
async def list_agencies(
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> list[AgencyOut]:
    return agencies_to_out(session, list(session.exec(select(Agency)).all()))


@router.post(
    "/agencies",
    response_model=AgencyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agency",
)
async def create_agency(
    body: AgencyCreate,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> AgencyOut:
    agency = Agency(name=body.name, created_by=principal.subject_id)
    session.add(agency)
    audit_service.record(session, actor=principal, action="AGENCY_ONBOARDED",
                         entity=f"agency:{agency.id}", after={"name": body.name})
    session.commit()
    session.refresh(agency)
    return agency_to_out(session, agency)


@router.get(
    "/agencies/{agency_id}",
    response_model=AgencyOut,
    summary="Get one agency",
    responses={404: {"description": "Agency not found"}},
)
async def get_agency(
    agency_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> AgencyOut:
    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="agency not found")
    return agency_to_out(session, agency)


@router.patch(
    "/agencies/{agency_id}",
    response_model=AgencyOut,
    summary="Rename / change agency status",
    responses={404: {"description": "Agency not found"}, 409: {"description": "Name already exists"}},
)
async def update_agency(
    agency_id: str,
    body: AgencyUpdate,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> AgencyOut:
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
    return agency_to_out(session, agency)


@router.delete(
    "/agencies/{agency_id}",
    response_model=AgencyOut,
    summary="Soft-delete an agency",
    responses={404: {"description": "Agency not found"}, 409: {"description": "Has open sheets"}},
)
async def soft_delete_agency(
    agency_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> AgencyOut:
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
    return agency_to_out(session, agency)


@router.post(
    "/users/assign-role",
    response_model=UserOut,
    summary="Quick-assign a role to a user by email",
    responses={404: {"description": "User not found"}, 422: {"description": "Invalid role"}},
)
async def assign_role(
    body: AssignRoleRequest,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    """Powers the admin 'Quick Role Assignment' widget — look the user up by email and set
    their role. Idempotent; audited."""
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    before = {"role": user.role}
    user.role = _parse_role(body.role)
    session.add(user)
    audit_service.record(session, actor=principal, action="ROLE_ASSIGNMENT",
                         entity=f"user:{user.id}", before=before, after={"role": user.role})
    session.commit()
    session.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut], summary="List users (filterable)")
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


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Get one user",
    responses={404: {"description": "User not found"}},
)
async def get_user(
    user_id: str,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin signup)",
    responses={409: {"description": "Email already exists"}, 422: {"description": "Invalid role"}},
)
async def create_user(
    body: UserCreate,
    principal: Principal = Depends(require(Capability.MANAGE_USERS)),
    session: Session = Depends(get_session),
) -> User:
    if session.exec(select(User).where(User.email == body.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="email already exists")

    # Enforce the same password policy as the reset flow — admins must not be able to seed
    # weak credentials (security: S-H5). SSO/no-password accounts skip this.
    if body.password:
        try:
            prs.validate_password(body.password, settings)
        except prs.PasswordPolicyError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    user = User(
        name=body.name, email=body.email, role=_parse_role(body.role), agency_id=body.agency_id,
        password_hash=_ph.hash(body.password) if body.password else None,
        source="manual" if body.password else "azure",
    )
    session.add(user)
    audit_service.record(session, actor=principal, action="USER_CREATED",
                         entity=f"user:{user.id}", after={"email": body.email, "role": body.role})
    session.commit()
    session.refresh(user)
    return user


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Update a user (role, email, agency, active, password)",
    responses={404: {"description": "User not found"}, 409: {"description": "Email already exists"}},
)
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


@router.delete(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Deactivate a user (soft delete)",
    responses={404: {"description": "User not found"}, 409: {"description": "Cannot deactivate self"}},
)
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


@router.post(
    "/escalations/run",
    summary="Run the SLA/aging escalation sweep now (alerts on sheets aging in review queues)",
)
async def run_escalations(
    principal: Principal = Depends(require(Capability.MANAGE_AGENCY)),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """On-demand trigger for the aging/escalation sweep (SCOPING §6.4, §8). Normally run on a
    schedule (`python -m app.jobs.escalation_job`); this lets an admin force a pass. Returns
    the run summary: how many waiting sheets were scanned and newly raised to warning/critical."""
    summary = escalation_service.run_escalations(session)
    audit_service.record(
        session, actor=principal, action="ESCALATION_SWEEP", after=summary.as_dict()
    )
    session.commit()
    return summary.as_dict()
