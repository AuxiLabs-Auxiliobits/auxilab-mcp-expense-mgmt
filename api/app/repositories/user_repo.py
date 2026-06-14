"""SQLModel-backed UserRepository implementing the auth provider's lookup contract.

Bridges the persistence model (app.models.User) to the issuer-agnostic UserRecord the
DbAuthProvider consumes (ADR-001) — so the provider never imports SQLModel.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.auth.db_provider import UserRecord
from app.models.user import User


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> UserRecord | None:
        user = self._session.exec(select(User).where(User.email == email)).first()
        if user is None or user.password_hash is None:
            return None
        return UserRecord(
            id=user.id,
            email=user.email,
            role=str(user.role),
            agency_id=user.agency_id,
            password_hash=user.password_hash,
            is_active=user.is_active,
        )
