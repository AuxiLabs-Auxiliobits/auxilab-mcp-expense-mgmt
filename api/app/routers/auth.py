"""Authentication routes. In `db` mode we mint tokens here; in `entra` mode login happens
at Entra's hosted flow and only `/me` is used (ADR-001)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.base import AuthError, AuthProvider
from app.auth.dependencies import current_principal, get_auth_provider
from app.principal import Principal
from app.schemas.dto import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, provider: AuthProvider = Depends(get_auth_provider)
) -> TokenResponse:
    try:
        token = await provider.authenticate(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return TokenResponse(access_token=token)


@router.get("/me", response_model=Principal)
async def me(principal: Principal = Depends(current_principal)) -> Principal:
    return principal
