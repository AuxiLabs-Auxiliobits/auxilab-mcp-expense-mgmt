"""Agency policy-document routes (SCOPING §7). Finance-only upload + maker-checker publish
of versioned policy docs that feed the per-agency RAG index the LLM finance approver reads.

RBAC: upload/publish/list require `UPDATE_AGENCY_POLICY_DOC` (Finance/Admin only — the
matrix already excludes Employee/Manager). The worker's index callback authenticates as the
AGENT service principal. Every action is audited (SCOPING §3.3, §7)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session

from app.auth.dependencies import require, require_role
from app.db import get_session
from app.models.policy import AgencyPolicy
from app.principal import Principal, Role
from app.rbac import scope as rbac_scope
from app.rbac.permissions import Capability
from app.schemas.dto import PolicyIndexedCallback, PolicyOut
from app.services import policy_service

router = APIRouter(prefix="/finance/policies", tags=["policy"])


def _to_out(policy: AgencyPolicy) -> PolicyOut:
    out = PolicyOut.model_validate(policy)
    out.status = policy_service.policy_status(policy)
    return out


@router.get("/{agency_id}", response_model=list[PolicyOut])
async def list_agency_policies(
    agency_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> list[PolicyOut]:
    """All policy-doc versions for an agency, newest first."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    return [_to_out(p) for p in policy_service.list_policies(session, agency_id)]


@router.post("/{agency_id}", response_model=PolicyOut, status_code=201)
async def upload_agency_policy(
    agency_id: str,
    file: UploadFile = File(...),
    effective_date: date | None = Form(default=None),
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> PolicyOut:
    """Upload a new policy-doc version (maker step). Stored to Blob (or local fallback);
    starts unpublished/unindexed until a different Finance/Admin publishes it."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    data = await file.read()
    policy = policy_service.upload_policy(
        session, actor=principal, agency_id=agency_id,
        filename=file.filename or "policy", data=data, effective_date=effective_date,
    )
    return _to_out(policy)


@router.post("/{agency_id}/{policy_id}/publish", response_model=PolicyOut)
async def publish_agency_policy(
    agency_id: str,
    policy_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> PolicyOut:
    """Publish (checker step) — enqueues the doc for RAG ingestion. Maker-checker SoD:
    the publisher must differ from the uploader."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    policy = policy_service.publish_policy(session, actor=principal, policy_id=policy_id)
    return _to_out(policy)


@router.post("/{policy_id}/indexed", response_model=PolicyOut)
async def report_indexed(
    policy_id: str,
    body: PolicyIndexedCallback,
    principal: Principal = Depends(require_role(Role.AGENT)),
    session: Session = Depends(get_session),
) -> PolicyOut:
    """Ingestion-worker callback: stamps `indexed_at` on success, audits failure otherwise."""
    policy = policy_service.mark_indexed(
        session, policy_id=policy_id, indexed=body.indexed, chunks=body.chunks,
        detail=body.detail,
    )
    return _to_out(policy)
