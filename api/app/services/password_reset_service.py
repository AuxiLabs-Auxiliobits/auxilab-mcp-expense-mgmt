"""Local password-reset flow (SCOPING §3). Secure-by-default:

  • No user enumeration — `request_reset` always reports the same generic outcome.
  • Tokens are single-use, time-limited, and stored only as a SHA-256 hash.
  • SSO-only accounts (federated, no local password) are never issued a reset link; the
    caller surfaces the "reset at your identity provider" path instead.
  • Password complexity is enforced on reset.

The whole flow is only meaningful in `db` (local) auth mode; in `entra`/`oidc` mode the API
advertises SSO via `login_methods()` and the frontend hides the local reset entirely.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from sqlmodel import Session, select

from app.config import Settings
from app.email.sender import EmailSender
from app.models.base import utcnow
from app.models.password_reset import PasswordResetToken
from app.models.user import User

logger = logging.getLogger("app.services.password_reset")
_ph = PasswordHasher()


class PasswordPolicyError(ValueError):
    """Raised when a new password fails the complexity policy."""


class ResetError(ValueError):
    """Raised when a reset token is invalid, expired, or already used."""


@dataclass
class LoginMethods:
    password: bool          # local email/password available
    sso: bool               # federated sign-in available
    sso_label: str          # e.g. "Microsoft"
    sso_reset_url: str      # where SSO users change their password


def login_methods(settings: Settings) -> LoginMethods:
    """Global (non-enumerating) description of how users sign in — drives the login UI."""
    # hybrid offers BOTH the local password form and the Microsoft SSO button.
    if settings.auth_provider == "hybrid":
        return LoginMethods(
            password=True,
            sso=True,
            sso_label="Microsoft",
            sso_reset_url="https://passwordreset.microsoftonline.com/",
        )
    is_sso = settings.auth_provider in ("entra", "oidc")
    label = "Microsoft" if settings.auth_provider == "entra" else "Single sign-on"
    reset_url = (
        "https://passwordreset.microsoftonline.com/"
        if settings.auth_provider == "entra"
        else ""
    )
    return LoginMethods(
        password=settings.auth_provider == "db",
        sso=is_sso,
        sso_label=label,
        sso_reset_url=reset_url,
    )


def validate_password(password: str, settings: Settings) -> None:
    """Enforce a pragmatic complexity policy. Raises PasswordPolicyError on failure."""
    if len(password) < settings.password_min_length:
        raise PasswordPolicyError(
            f"Password must be at least {settings.password_min_length} characters."
        )
    if not any(c.islower() for c in password):
        raise PasswordPolicyError("Password must include a lowercase letter.")
    if not any(c.isupper() for c in password):
        raise PasswordPolicyError("Password must include an uppercase letter.")
    if not any(c.isdigit() for c in password):
        raise PasswordPolicyError("Password must include a number.")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    """Coerce a possibly-naive DB datetime to UTC-aware for safe comparison."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def request_reset(session: Session, settings: Settings, sender: EmailSender, email: str) -> None:
    """Issue a reset link for a local account. Always returns None (no enumeration);
    silently does nothing for unknown or SSO-only accounts."""
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    # Only local accounts (with a password) get a reset link; SSO-only users have none.
    if user is None or not user.is_active or user.password_hash is None:
        logger.info("Reset requested for non-local/unknown email; no link issued.")
        return

    # Invalidate any outstanding tokens for this user (single live link at a time).
    for stale in session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
    ).all():
        stale.used_at = utcnow()
        session.add(stale)

    raw = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=utcnow() + timedelta(minutes=settings.reset_token_ttl_minutes),
    )
    session.add(token)
    session.commit()

    link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw}"
    sender.send(
        to=user.email,
        subject="Reset your Auxilab password",
        body=(
            f"Hi {user.name},\n\n"
            "We received a request to reset your Auxilab password. Use the link below "
            f"(valid for {settings.reset_token_ttl_minutes} minutes, single use):\n\n"
            f"{link}\n\n"
            "If you didn't request this, you can safely ignore this email — your password "
            "won't change.\n\n— Auxilab Expense Management"
        ),
    )
    logger.info("Issued password-reset link to %s", user.email)


def reset_password(session: Session, settings: Settings, raw_token: str, new_password: str) -> None:
    """Consume a reset token and set a new password. Raises ResetError / PasswordPolicyError."""
    token = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(raw_token))
    ).first()
    # SQLite returns naive datetimes — coerce to UTC-aware before comparing.
    expired = token is not None and _as_utc(token.expires_at) < utcnow()
    if token is None or token.used_at is not None or expired:
        raise ResetError("This reset link is invalid or has expired. Please request a new one.")

    user = session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise ResetError("This reset link is invalid or has expired. Please request a new one.")

    validate_password(new_password, settings)  # may raise PasswordPolicyError

    user.password_hash = _ph.hash(new_password)
    token.used_at = utcnow()  # single-use
    session.add(user)
    session.add(token)
    session.commit()
    logger.info("Password reset completed for %s", user.email)
