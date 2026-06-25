"""Authentication routes. In `db` mode we mint tokens here; in `entra` mode login happens
at Entra's hosted flow and only `/me` is used (ADR-001)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.auth.base import AuthError, AuthProvider
from app.auth.dependencies import current_principal, get_auth_provider
from app.db import get_session
from app.models.agency import Agency
from app.models.user import User
from app.principal import Principal
from app.schemas.dto import LoginRequest, MeOut, TokenResponse

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Bad credentials or invalid/expired token"}},
)


@router.post("/login", response_model=TokenResponse, summary="Log in (JSON) and get a bearer token")
async def login(
    body: LoginRequest, provider: AuthProvider = Depends(get_auth_provider)
) -> TokenResponse:
    """Authenticate with an email + password (JSON body) and receive a JWT bearer token.

    Used by programmatic clients and the Postman collection. For the Swagger **Authorize**
    button use `POST /auth/token` instead (same credentials, form-encoded). `db` mode only —
    in `entra` mode the token is minted by Entra's hosted login (ADR-001)."""
    try:
        token = await provider.authenticate(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return TokenResponse(access_token=token)


@router.post("/token", response_model=TokenResponse, summary="OAuth2 token endpoint (for Swagger Authorize)")
async def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    provider: AuthProvider = Depends(get_auth_provider),
) -> TokenResponse:
    """Form-based OAuth2 password grant powering Swagger's **Authorize** dialog.

    Enter a demo email as the **username** (e.g. `employee@demo.local`) and `demo` as the
    **password**; Swagger then attaches the returned token to every request automatically.
    Functionally identical to `POST /auth/login`."""
    try:
        access = await provider.authenticate(form.username, form.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return TokenResponse(access_token=access)


@router.get("/me", response_model=MeOut, summary="Current authenticated user")
async def me(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> MeOut:
    """Return the caller's identity for the UI: the token's principal plus the human-readable
    display name and agency name (looked up from the DB) so the frontend shows a name, not the
    email. Handy first call to confirm Authorize worked and to see your role."""
    user = session.get(User, principal.subject_id)
    agency = session.get(Agency, principal.agency_id) if principal.agency_id else None
    return MeOut(
        subject_id=principal.subject_id,
        email=principal.email,
        name=(user.name if user else None) or principal.email or principal.subject_id,
        role=principal.role,
        agency_id=principal.agency_id,
        agency_name=agency.name if agency else None,
        scope=principal.scope,
    )
