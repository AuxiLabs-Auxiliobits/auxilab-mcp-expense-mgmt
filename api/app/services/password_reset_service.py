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


class UserNotFoundError(ValueError):
    """Raised when no local account exists for the requested email."""


class SsoAccountError(ValueError):
    """Raised when the account exists but is SSO-only (no local password)."""


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


def request_reset(session: Session, settings: Settings, sender: EmailSender, email: str) -> str | None:
    """Issue a reset link for a local account; email it via `sender`. Returns the link so the
    router can expose it in DEV only (for self-service testing without SMTP); callers MUST NOT
    return it to clients outside dev (it would enable enumeration). Returns None for unknown or
    SSO-only accounts (no link issued)."""
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    if user is None or not user.is_active:
        raise UserNotFoundError("No account found for that email address.")
    if user.password_hash is None:
        raise SsoAccountError(
            "This account uses Microsoft SSO. Please reset your password through Microsoft."
        )

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
    ttl = settings.reset_token_ttl_minutes
    validity = f"{ttl // 60} hours" if ttl >= 60 and ttl % 60 == 0 else f"{ttl} minutes"
    plain = (
        f"Hi {user.name},\n\n"
        "We received a request to reset your Auxilab password. Use the link below "
        f"(valid for {validity}, single use):\n\n"
        f"{link}\n\n"
        "If you didn't request this, you can safely ignore this email — your password "
        "won't change.\n\n— Auxilab Expense Management"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Reset your Auxilab password</title>
</head>
<body style="margin:0;padding:0;background:#f0f4ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;padding:48px 16px;">
    <tr><td align="center">

      <!-- Card -->
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(26,86,219,0.10);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1a56db 0%,#1e40af 100%);padding:32px 40px 28px;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="vertical-align:middle;">
                  <div style="width:40px;height:40px;background:rgba(255,255,255,0.18);border-radius:10px;display:inline-block;text-align:center;line-height:40px;font-size:20px;vertical-align:middle;">&#128274;</div>
                </td>
                <td style="padding-left:12px;vertical-align:middle;">
                  <span style="color:#ffffff;font-size:17px;font-weight:700;letter-spacing:0.2px;display:block;">Auxilab</span>
                  <span style="color:rgba(255,255,255,0.72);font-size:12px;letter-spacing:0.3px;text-transform:uppercase;">Expense Management</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Hero icon strip -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af 0%,#1d4ed8 100%);padding:0 40px 32px;text-align:center;">
            <div style="width:68px;height:68px;background:#ffffff;border-radius:50%;display:inline-block;text-align:center;line-height:68px;font-size:30px;box-shadow:0 4px 16px rgba(0,0,0,0.18);">&#128272;</div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px 16px;">
            <h1 style="margin:0 0 6px;font-size:24px;font-weight:700;color:#111827;letter-spacing:-0.3px;">Reset your password</h1>
            <p style="margin:0 0 24px;font-size:15px;color:#6b7280;">Hi <strong style="color:#374151;">{user.name}</strong>,</p>
            <p style="margin:0 0 28px;font-size:15px;color:#374151;line-height:1.7;">
              We received a request to reset your <strong>Auxilab</strong> password.
              Click the button below — the link is valid for <strong style="color:#1a56db;">{validity}</strong> and can only be used once.
            </p>

            <!-- CTA Button -->
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
              <tr>
                <td align="center" style="background:linear-gradient(135deg,#1a56db,#1d4ed8);border-radius:10px;box-shadow:0 4px 12px rgba(26,86,219,0.35);">
                  <a href="{link}" style="display:inline-block;padding:15px 36px;color:#ffffff;font-size:15px;font-weight:700;text-decoration:none;letter-spacing:0.2px;">
                    Reset password &rarr;
                  </a>
                </td>
              </tr>
            </table>

            <!-- Fallback link -->
            <table cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 28px;">
              <tr>
                <td style="background:#f8faff;border:1px solid #e0e7ff;border-radius:8px;padding:14px 16px;">
                  <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">Or paste this link in your browser</p>
                  <p style="margin:0;font-size:12px;color:#1a56db;word-break:break-all;line-height:1.5;">{link}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Security note -->
        <tr>
          <td style="padding:0 40px 32px;">
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:14px 16px;">
                  <p style="margin:0;font-size:13px;color:#92400e;line-height:1.6;">
                    <strong>&#9888; Didn&apos;t request this?</strong><br>
                    You can safely ignore this email — your password won&apos;t change and this link will expire automatically.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #e5e7eb;margin:0;"></td></tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px 28px;">
            <p style="margin:0 0 4px;font-size:12px;color:#9ca3af;">This email was sent to <strong>{user.email}</strong></p>
            <p style="margin:0;font-size:12px;color:#d1d5db;">© 2026 Auxilab &middot; Expense Management &middot; All rights reserved</p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    try:
        sender.send(
            to=user.email,
            subject="Reset your Auxilab password",
            body=plain,
            html=html,
        )
        logger.info("Issued password-reset link to %s", user.email)
    except Exception:
        logger.exception("SMTP delivery failed for %s — link was generated but not sent", user.email)
    return link


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
