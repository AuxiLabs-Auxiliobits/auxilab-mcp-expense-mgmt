"""Current-user settings (SCOPING §6.4). Read/write the signed-in user's preferences
(e.g. notification toggles) so the Settings page persists choices."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth.dependencies import current_principal
from app.db import get_session
from app.models.user import User
from app.principal import Principal
from app.schemas.dto import PreferencesIn, PreferencesOut

router = APIRouter(
    prefix="/me",
    tags=["settings"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


def _user_or_404(session: Session, principal: Principal) -> User:
    user = session.get(User, principal.subject_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


@router.get("/preferences", response_model=PreferencesOut, summary="My settings/preferences")
async def get_preferences(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> PreferencesOut:
    user = _user_or_404(session, principal)
    return PreferencesOut(preferences=user.preferences or {})


@router.put("/preferences", response_model=PreferencesOut, summary="Save my settings/preferences")
async def put_preferences(
    body: PreferencesIn,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> PreferencesOut:
    user = _user_or_404(session, principal)
    # Persist only the known toggles, keeping the camelCase keys the client reads, and
    # dropping any unset/unknown keys so the JSON column stays a clean boolean map.
    user.preferences = body.preferences.model_dump(by_alias=True, exclude_none=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return PreferencesOut(preferences=user.preferences or {})
