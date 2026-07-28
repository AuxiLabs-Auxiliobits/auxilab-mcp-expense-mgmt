"""Policy Assistant route (SCOPING §7, §11). Agency-scoped RAG: retrieves the caller's own
agency policy and answers via Azure AI Foundry (offline composer when Foundry isn't wired).
Every role may ask (RAG_QUERY); the agency is taken from the token, never the client."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.dependencies import _bearer, current_principal, require
from app.db import get_session
from app.principal import Principal
from app.rbac.permissions import Capability
from app.schemas.dto import AssistantAnswerOut, AssistantCitation, AssistantQuery
from app.services import assistant_bridge, assistant_service

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


# --- In-app AI Assistant (MCP bridge) ------------------------------------------------------ #
# These endpoints power the conversational assistant in the web app. They never touch business
# logic directly: every action flows through the existing `expense_mcp` MCP tools, carrying the
# caller's token, so RBAC / agency-scope / SoD / audit are enforced by the API as usual.


class AssistantChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # opaque conversation state echoed back each turn (host-owned memory): pending action,
    # last numbered list, current screen. No server-side session store.
    context: dict | None = None


class AssistantSuggestIn(BaseModel):
    screen: str | None = None


@router.post("/chat", summary="Chat with the in-app AI Assistant (drives MCP tools)")
async def assistant_chat(
    body: AssistantChatIn,
    principal: Principal = Depends(current_principal),
    token: str = Depends(_bearer),
) -> dict:
    """Natural-language → MCP tool calls. Returns a business-friendly reply plus explainability
    (`tools_used`, `actions`), guided-flow state (`needs`, `pending`), follow-up `context`, and
    role-aware `suggestions`. The MCP tools run in a threadpool (sync HTTP clients)."""
    return await run_in_threadpool(
        assistant_bridge.handle_chat, token, principal, body.message, body.context
    )


@router.post("/suggestions", summary="Context-aware assistant suggestions for the current screen")
async def assistant_suggestions(
    body: AssistantSuggestIn,
    principal: Principal = Depends(current_principal),
) -> dict:
    return {"suggestions": assistant_bridge.suggestions_for_screen(principal.role, body.screen)}
