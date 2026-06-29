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
from app.config import settings
from app.models.agency import Agency
from app.models.attachment import ScanStatus
from app.models.base import utcnow
from app.models.policy import AgencyPolicy
from app.principal import Principal
from app.services import audit_service, malware_scan_service


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

    if malware_scan_service.scan_bytes(data, filename) == ScanStatus.INFECTED:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Malware detected — file rejected",
        )

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

    # No async worker wired (Service Bus absent) but Azure Search is configured → ingest the
    # doc synchronously here so it becomes RAG-searchable immediately and the panel shows it
    # as "indexed". Best-effort: an ingestion failure is audited but doesn't fail the publish.
    if not sent and settings.azure_search_enabled:
        from app.services import policy_ingest_service  # noqa: PLC0415

        try:
            count = policy_ingest_service.ingest_policy_inline(
                blob_uri=policy.doc_blob_uri or "",
                agency_id=policy.agency_id,
                policy_version=str(policy.version),
                settings=settings,
            )
            policy.indexed_at = utcnow()
            session.add(policy)
            audit_service.record(
                session, action="POLICY_INDEXED", entity=f"agency_policy:{policy.id}",
                agency_id=policy.agency_id,
                after={"version": policy.version, "chunks": count, "inline": True},
            )
        except Exception as exc:  # noqa: BLE001 — never fail the publish on an ingestion error
            audit_service.record(
                session, action="POLICY_INDEX_FAILED", entity=f"agency_policy:{policy.id}",
                agency_id=policy.agency_id,
                after={"version": policy.version, "detail": str(exc)[:500], "inline": True},
            )

    session.commit()
    session.refresh(policy)
    return policy


def policy_content(session: Session, policy_id: str) -> dict[str, str]:
    """Extract and return the plain text of a stored policy doc for the read-only viewer.
    Best-effort: returns an empty string with a note if the source can't be read."""
    policy = _get_or_404(session, policy_id)
    if not policy.doc_blob_uri:
        return {"content": "", "detail": "no document stored for this version"}
    try:
        from app.services import policy_ingest_service  # noqa: PLC0415

        text = policy_ingest_service.extract_policy_text(policy.doc_blob_uri, settings)
        # DOCX/PDF without Doc Intelligence → raw binary decoded as UTF-8 → starts with "PK".
        # Return the raw bytes so the UI can detect binary and warn the user; don't try to
        # show garbage as policy text.
        return {"content": text, "version": str(policy.version)}
    except Exception as exc:  # noqa: BLE001 — viewer is best-effort
        return {"content": "", "detail": f"could not read document: {exc}"}


def delete_policy(session: Session, *, actor: Principal, agency_id: str, policy_id: str) -> None:
    """Delete a policy doc and purge its Azure AI Search chunks (if already indexed).
    Audited; raises 404 if not found or agency_id doesn't match."""
    policy = _get_or_404(session, policy_id)
    if policy.agency_id != agency_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="policy not found")

    chunks_deleted = 0
    if policy.indexed_at is not None and settings.azure_search_enabled:
        from app.services import policy_ingest_service  # noqa: PLC0415
        try:
            chunks_deleted = policy_ingest_service.purge_policy_chunks(
                policy.agency_id, str(policy.version), settings
            )
        except Exception as exc:  # noqa: BLE001 — audit but don't block deletion
            audit_service.record(
                session, actor=actor, action="POLICY_PURGE_FAILED",
                entity=f"agency_policy:{policy.id}", agency_id=agency_id,
                after={"version": policy.version, "detail": str(exc)[:500]},
            )

    audit_service.record(
        session, actor=actor, action="POLICY_DELETED",
        entity=f"agency_policy:{policy.id}", agency_id=agency_id,
        after={"version": policy.version, "chunks_deleted": chunks_deleted},
    )
    session.delete(policy)
    session.commit()


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
