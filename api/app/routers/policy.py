"""Agency policy-document routes (SCOPING §7). Finance-only upload + maker-checker publish
of versioned policy docs that feed the per-agency RAG index the LLM finance approver reads.

RBAC: upload/publish/list require `UPDATE_AGENCY_POLICY_DOC` (Finance/Admin only — the
matrix already excludes Employee/Manager). The worker's index callback authenticates as the
AGENT service principal. Every action is audited (SCOPING §3.3, §7)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session, select

from app.auth.dependencies import require, require_role
from app.db import get_session
from app.config import settings
from app.models.audit import AuditLog
from app.models.policy import AgencyPolicy
from app.principal import Principal, Role
from app.rbac import scope as rbac_scope
from app.rbac.permissions import Capability
from app.schemas.dto import PolicyChunkOut, PolicyEventOut, PolicyIndexedCallback, PolicyIndexSummaryOut, PolicyOut
from app.services import policy_service

router = APIRouter(
    prefix="/finance/policies",
    tags=["policy"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Insufficient role (Finance/Admin; Agent for the index callback)"},
    },
)


def _to_out(policy: AgencyPolicy) -> PolicyOut:
    out = PolicyOut.model_validate(policy)
    out.status = policy_service.policy_status(policy)
    return out


@router.get("/{agency_id}", response_model=list[PolicyOut], summary="List policy-doc versions")
async def list_agency_policies(
    agency_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> list[PolicyOut]:
    """All policy-doc versions for an agency, newest first."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    return [_to_out(p) for p in policy_service.list_policies(session, agency_id)]


@router.post(
    "/{agency_id}",
    response_model=PolicyOut,
    status_code=201,
    summary="Upload a policy doc (maker step)",
)
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


@router.get(
    "/{agency_id}/{policy_id}/content",
    summary="Extracted plain-text of a policy doc (read-only viewer)",
    responses={404: {"description": "Policy not found"}},
)
async def policy_content(
    agency_id: str,
    policy_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Return the extracted text of a stored policy doc so the UI can preview the actual
    RAG-indexed source (not a static sample). Reuses the ingestion text extractor."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    return policy_service.policy_content(session, policy_id)


@router.post(
    "/{agency_id}/{policy_id}/publish",
    response_model=PolicyOut,
    summary="Publish a policy doc (checker step, SoD)",
)
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


@router.get(
    "/{agency_id}/{policy_id}/log",
    response_model=list[PolicyEventOut],
    summary="Ordered ingestion audit events for a policy version",
)
async def policy_ingest_log(
    agency_id: str,
    policy_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> list[PolicyEventOut]:
    """Audit trail for one policy version: upload → publish → indexed/failed, oldest first."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    events = session.exec(
        select(AuditLog)
        .where(AuditLog.entity == f"agency_policy:{policy_id}")
        .order_by(AuditLog.timestamp.asc())
    ).all()
    return [
        PolicyEventOut(id=e.id, action=e.action, after=e.after, timestamp=e.timestamp)
        for e in events
    ]


@router.delete(
    "/{agency_id}/{policy_id}",
    status_code=204,
    summary="Delete a policy doc and purge its Azure AI Search chunks",
)
async def delete_agency_policy(
    agency_id: str,
    policy_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
    session: Session = Depends(get_session),
) -> None:
    """Hard-delete a policy version from the DB and remove all its chunks from the Azure AI
    Search index. Finance/Admin only. Audited as POLICY_DELETED."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    policy_service.delete_policy(session, actor=principal, agency_id=agency_id, policy_id=policy_id)


@router.get(
    "/{agency_id}/index-summary",
    response_model=PolicyIndexSummaryOut,
    summary="Per-version chunk count summary for an agency in Azure AI Search",
)
async def agency_index_summary(
    agency_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
) -> PolicyIndexSummaryOut:
    """Returns how many chunks are indexed per policy_version for this agency.
    Useful for spotting stale versions (old seed chunks vs. newly uploaded content)."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    if not settings.azure_search_enabled:
        return PolicyIndexSummaryOut(agency_id=agency_id, versions=[], total_chunks=0)
    try:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415
        from azure.search.documents import SearchClient  # noqa: PLC0415

        credential = (
            AzureKeyCredential(settings.search_api_key)
            if settings.search_api_key
            else __import__("azure.identity", fromlist=["DefaultAzureCredential"]).DefaultAzureCredential()
        )
        client = SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index_name,
            credential=credential,
        )
        safe_id = agency_id.replace("'", "''")
        results = client.search(
            search_text="*",
            filter=f"agency_id eq '{safe_id}'",
            select=["policy_version"],
            top=500,
        )
        version_map: dict[str, dict] = {}
        for r in results:
            v = str(r.get("policy_version", "unknown"))
            if v not in version_map:
                # content_vector is not a retrievable field — treat any indexed chunk as
                # having vectors (the ingest pipeline embeds before upserting).
                version_map[v] = {"version": v, "chunks": 0, "has_vectors": True}
            version_map[v]["chunks"] += 1

        versions = sorted(version_map.values(), key=lambda x: x["version"], reverse=True)
        return PolicyIndexSummaryOut(
            agency_id=agency_id,
            versions=versions,
            total_chunks=sum(v["chunks"] for v in versions),
        )
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException, status as http_status  # noqa: PLC0415
        raise HTTPException(http_status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/{agency_id}/chunks",
    response_model=list[PolicyChunkOut],
    summary="List all indexed chunks for an agency from Azure AI Search",
)
async def list_agency_chunks(
    agency_id: str,
    principal: Principal = Depends(require(Capability.UPDATE_AGENCY_POLICY_DOC)),
) -> list[PolicyChunkOut]:
    """Query Azure AI Search and return every chunk indexed for this agency — useful for
    verifying ingestion: content, chunk index, version, and whether a vector is present."""
    rbac_scope.assert_can_manage_agency_policy(principal, agency_id)
    if not settings.azure_search_enabled:
        return []
    try:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415
        from azure.search.documents import SearchClient  # noqa: PLC0415

        credential = AzureKeyCredential(settings.search_api_key) if settings.search_api_key else None
        if credential is None:
            from azure.identity import DefaultAzureCredential  # noqa: PLC0415
            credential = DefaultAzureCredential()

        client = SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index_name,
            credential=credential,
        )
        safe_id = agency_id.replace("'", "''")
        results = client.search(
            search_text="*",
            filter=f"agency_id eq '{safe_id}'",
            select=["id", "agency_id", "policy_version", "chunk_index", "content"],
            order_by=["policy_version desc", "chunk_index asc"],
            top=200,
        )
        chunks = []
        for r in results:
            chunks.append(PolicyChunkOut(
                id=str(r.get("id", "")),
                agency_id=str(r.get("agency_id", "")),
                policy_version=str(r.get("policy_version", "")),
                chunk_index=int(r.get("chunk_index", 0)),
                content=str(r.get("content", "")),
                has_vector=True,  # content_vector is non-retrievable; any indexed chunk was embedded
            ))
        return chunks
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException, status as http_status  # noqa: PLC0415
        raise HTTPException(http_status.HTTP_502_BAD_GATEWAY, detail=f"Azure AI Search error: {exc}") from exc


@router.post(
    "/{policy_id}/indexed",
    response_model=PolicyOut,
    summary="Ingestion-worker callback (Agent role)",
)
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
