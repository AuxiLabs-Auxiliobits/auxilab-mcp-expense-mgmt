"""Authentication routes. In `db` mode we mint tokens here; in `entra` mode login happens
at Entra's hosted flow and only `/me` is used (ADR-001)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.auth.base import AuthError, AuthProvider, UserNotFoundError
from app.auth.dependencies import current_principal, get_auth_provider
from app.config import settings
from app.rate_limit import limiter
from app.db import get_session
from app.email.sender import get_email_sender
from app.models.agency import Agency
from app.models.user import User
from app.principal import Principal
from app.schemas.dto import (
    AuthMethodOut,
    ForgotPasswordRequest,
    LoginMethodsOut,
    LoginRequest,
    MeOut,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services import password_reset_service as prs

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Bad credentials or invalid/expired token"}},
)


@router.post("/login", response_model=TokenResponse, summary="Log in (JSON) and get a bearer token")
@limiter.limit(settings.rate_limit_auth)
async def login(
    request: Request, body: LoginRequest, provider: AuthProvider = Depends(get_auth_provider)
) -> TokenResponse:
    """Authenticate with an email + password (JSON body) and receive a JWT bearer token.

    Used by programmatic clients and the Postman collection. For the Swagger **Authorize**
    button use `POST /auth/token` instead (same credentials, form-encoded). `db` mode only —
    in `entra` mode the token is minted by Entra's hosted login (ADR-001)."""
    try:
        token = await provider.authenticate(body.email, body.password)
    except UserNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found for that email address.") from e
    except AuthError as e:
        # 403 = account exists but is disabled (distinct from 401 = wrong credentials).
        # The frontend auth.ts maps 403 → AccountDisabledError → deactivation message.
        if "disabled" in str(e).lower():
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return TokenResponse(access_token=token)


@router.post("/token", response_model=TokenResponse, summary="OAuth2 token endpoint (for Swagger Authorize)")
@limiter.limit(settings.rate_limit_auth)
async def token(
    request: Request,
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


@router.get("/login-methods", response_model=LoginMethodsOut, summary="Which sign-in methods are enabled")
async def login_methods() -> LoginMethodsOut:
    """Public: tells the login UI whether local password login and/or SSO are enabled, and
    where SSO users reset their password. Global config — never leaks whether an email exists."""
    m = prs.login_methods(settings)
    return LoginMethodsOut(password=m.password, sso=m.sso, sso_label=m.sso_label, sso_reset_url=m.sso_reset_url)


@router.get("/auth-method", response_model=AuthMethodOut, summary="Login route for a given email (hybrid)")
async def auth_method(email: str, session: Session = Depends(get_session)) -> AuthMethodOut:
    """The hybrid login form calls this when the user submits: it returns "azure" for accounts
    that must sign in via Microsoft SSO, else "password" (local check). Unknown / manual / empty
    all resolve to "password", so this never reveals whether an arbitrary email exists — only
    whether a known account is Azure-backed."""
    if settings.auth_provider != "hybrid":
        # Single-mode deployments don't route per-email; mirror the global method.
        m = prs.login_methods(settings)
        return AuthMethodOut(method="azure" if m.sso and not m.password else "password")
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    is_azure = user is not None and (user.source or "").lower() == "azure"
    return AuthMethodOut(method="azure" if is_azure else "password")


@router.post("/forgot-password", response_model=MessageResponse, summary="Request a local password reset")
@limiter.limit(settings.rate_limit_forgot)
async def forgot_password(
    request: Request, body: ForgotPasswordRequest, session: Session = Depends(get_session)
) -> MessageResponse:
    """Email a single-use, time-limited reset link for a local account. Always returns the
    same generic message (no user enumeration); SSO-only accounts get no link. In DEV only,
    the link is echoed back (`dev_reset_link`) so the flow is testable without an SMTP server."""
    try:
        link = prs.request_reset(session, settings, get_email_sender(settings), body.email)
    except prs.UserNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except prs.SsoAccountError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return MessageResponse(
        message="A password-reset link is on its way. It is valid for 24 hours and can be used once.",
        dev_reset_link=link if settings.environment == "dev" else None,
    )


@router.post("/reset-password", response_model=MessageResponse, summary="Set a new password from a reset token")
async def reset_password(
    body: ResetPasswordRequest, session: Session = Depends(get_session)
) -> MessageResponse:
    """Consume a reset token and set a new password (single-use; complexity enforced)."""
    try:
        prs.reset_password(session, settings, body.token, body.new_password)
    except prs.PasswordPolicyError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    except prs.ResetError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return MessageResponse(message="Your password has been reset. You can now sign in.")


@router.get("/me", response_model=MeOut, summary="Current authenticated principal")
async def me(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> MeOut:
    """Return the caller's identity for the UI: id, email, role, agency, scope — plus the
    display `name` and `agency_name` resolved from the DB (the token carries only ids). Handy
    first call to confirm Authorize worked and to see your role."""
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
