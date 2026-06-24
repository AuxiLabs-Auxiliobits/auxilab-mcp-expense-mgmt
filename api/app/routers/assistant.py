"""Policy Assistant route (SCOPING §7, §11). Agency-scoped RAG: retrieves the caller's own
agency policy and answers via Azure AI Foundry (offline composer when Foundry isn't wired).
Every role may ask (RAG_QUERY); the agency is taken from the token, never the client."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.dependencies import require
from app.db import get_session
from app.principal import Principal
from app.rbac.permissions import Capability
from app.schemas.dto import AssistantAnswerOut, AssistantCitation, AssistantQuery
from app.services import assistant_service

router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


@router.post(
    "/policy",
    response_model=AssistantAnswerOut,
    summary="Ask the agency Policy Assistant (RAG over your agency's policy)",
)
async def policy_query(
    body: AssistantQuery,
    principal: Principal = Depends(require(Capability.RAG_QUERY)),
    session: Session = Depends(get_session),
) -> AssistantAnswerOut:
    """Answer a policy question grounded in the caller's own agency policy. Uses Azure Foundry
    + Azure AI Search when configured; otherwise a deterministic offline composer. Routes to a
    human when no clause covers the question."""
    result = assistant_service.answer_policy_question(session, principal, body.query)
    return AssistantAnswerOut(
        answer=result.answer,
        citations=[
            AssistantCitation(id=c.id, title=c.title, text=c.text, source=c.source)
            for c in result.citations
        ],
        policy_version=result.policy_version,
        routed_to_human=result.routed_to_human,
        model_version=result.model_version,
    )
