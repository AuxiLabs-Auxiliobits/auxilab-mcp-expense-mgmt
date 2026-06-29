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
        return self._to_record(user)

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        """Look up a user by id — used to re-check account status on every request so a
        deactivated user's existing token stops working immediately."""
        user = self._session.get(User, user_id)
        return self._to_record(user) if user else None

    @staticmethod
    def _to_record(user: User) -> UserRecord:
        return UserRecord(
            id=user.id,
            email=user.email,
            role=str(user.role),
            agency_id=user.agency_id,
            password_hash=user.password_hash or "",
            is_active=user.is_active,
        )
