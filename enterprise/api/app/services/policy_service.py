"""Agency policy-document lifecycle (SCOPING §7). Finance uploads a versioned policy doc,
a *different* Finance/Admin publishes it (maker-checker), which enqueues it for RAG
ingestion; the ingestion worker reports back when the AI Search upsert completes.

Every step is appended to the audit log. Agency policy is the security boundary the LLM
finance approver evaluates against, so nothing here is silent: upload, publish, and index
each leave a record.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app import messaging, storage
from app.models.agency import Agency
from app.models.base import utcnow
from app.models.policy import AgencyPolicy
from app.principal import Principal
from app.services import audit_service


def policy_status(policy: AgencyPolicy) -> str:
    """Derived lifecycle state for the API surface."""
    if policy.indexed_at is not None:
        return "indexed"
    if policy.published_by is not None:
        return "published"
    return "draft"


def _get_or_404(session: Session, policy_id: str) -> AgencyPolicy:
    policy = session.get(AgencyPolicy, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="policy not found")
    return policy


def list_policies(session: Session, agency_id: str) -> list[AgencyPolicy]:
    return list(
        session.exec(
            select(AgencyPolicy)
            .where(AgencyPolicy.agency_id == agency_id)
            .order_by(AgencyPolicy.version.desc())
        ).all()
    )


def upload_policy(
    session: Session,
    *,
    actor: Principal,
    agency_id: str,
    filename: str,
    data: bytes,
    effective_date: date | None,
) -> AgencyPolicy:
    """Store a new policy-doc version for an agency (maker step). The new version is the
    current max for the agency + 1; it starts unpublished/unindexed (SCOPING §7)."""
    if session.get(Agency, agency_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="agency not found")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="empty file")

    latest = session.exec(
        select(AgencyPolicy)
        .where(AgencyPolicy.agency_id == agency_id)
        .order_by(AgencyPolicy.version.desc())
    ).first()
    next_version = (latest.version + 1) if latest else 1

    blob_uri = storage.upload_policy_blob(agency_id, next_version, filename, data)
    policy = AgencyPolicy(
        agency_id=agency_id,
        version=next_version,
        doc_blob_uri=blob_uri,
        effective_date=effective_date,
        created_by=actor.subject_id,
    )
    session.add(policy)
    audit_service.record(
        session, actor=actor, action="POLICY_UPLOADED", entity=f"agency_policy:{policy.id}",
        agency_id=agency_id,
        after={"version": next_version, "filename": filename, "blob_uri": blob_uri},
    )
    session.commit()
    session.refresh(policy)
    return policy


def publish_policy(session: Session, *, actor: Principal, policy_id: str) -> AgencyPolicy:
    """Checker step: a *different* Finance/Admin publishes the uploaded doc, which enqueues
    it for RAG ingestion. Maker-checker SoD — the publisher may not be the uploader."""
    policy = _get_or_404(session, policy_id)

    if policy.published_by is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="policy already published")
    if policy.created_by is not None and policy.created_by == actor.subject_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="maker-checker: the publisher must differ from the uploader",
        )

    policy.published_by = actor.subject_id
    session.add(policy)
    sent = messaging.enqueue_ingestion(
        agency_id=policy.agency_id,
        policy_version=str(policy.version),
        blob_uri=policy.doc_blob_uri or "",
        policy_id=policy.id,
    )
    audit_service.record(
        session, actor=actor, action="POLICY_PUBLISHED", entity=f"agency_policy:{policy.id}",
        agency_id=policy.agency_id,
        after={"version": policy.version, "enqueued_for_ingestion": sent},
    )
    session.commit()
    session.refresh(policy)
    return policy


def mark_indexed(
    session: Session, *, policy_id: str, indexed: bool, chunks: int, detail: str | None
) -> AgencyPolicy:
    """Ingestion-worker callback (authenticated as the AGENT principal). On success stamps
    `indexed_at`; on failure records POLICY_INDEX_FAILED so a half-index is never silent."""
    policy = _get_or_404(session, policy_id)

    if indexed:
        policy.indexed_at = utcnow()
        session.add(policy)
        audit_service.record(
            session, action="POLICY_INDEXED", entity=f"agency_policy:{policy.id}",
            agency_id=policy.agency_id, after={"version": policy.version, "chunks": chunks},
        )
    else:
        audit_service.record(
            session, action="POLICY_INDEX_FAILED", entity=f"agency_policy:{policy.id}",
            agency_id=policy.agency_id, after={"version": policy.version, "detail": detail},
        )
    session.commit()
    session.refresh(policy)
    return policy
