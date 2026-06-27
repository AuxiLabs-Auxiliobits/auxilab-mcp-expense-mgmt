"""Password-reset tokens for local (DbAuthProvider) accounts.

We store only a SHA-256 *hash* of the token — the raw token lives only in the emailed link,
so a database leak can't be used to reset anyone's password. Tokens are single-use
(`used_at`) and time-limited (`expires_at`).
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
