"""DbAuthProvider — NOW. Verifies password (argon2id) against the users table and
mints our own HS256 JWT whose claims mirror Entra's shape (see ADR-001).

The user lookup is abstracted behind `UserRepository` so this works against the real
Postgres schema (docs/schema-users.sql) without this module importing a DB driver.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.auth.base import AuthError, AuthProvider, UserNotFoundError
from app.principal import Principal, Role, scope_for

_ph = PasswordHasher()


@dataclass
class UserRecord:
    id: str
    email: str
    role: str
    agency_id: str | None
    password_hash: str
    is_active: bool


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> UserRecord | None: ...
    async def get_by_id(self, user_id: str) -> UserRecord | None: ...


class DbAuthProvider(AuthProvider):
    def __init__(self, users: UserRepository, secret: str, algorithm: str, ttl_seconds: int):
        self._users = users
        self._secret = secret
        self._algorithm = algorithm
        self._ttl = ttl_seconds

    async def authenticate(self, email: str, password: str) -> str:
        user = await self._users.get_by_email(email)
        # Always run a verify to keep timing constant regardless of whether the user exists.
        try:
            _ph.verify(user.password_hash if user else _DUMMY_HASH, password)
        except VerifyMismatchError as e:
            raise AuthError("invalid credentials") from e
        if user is None:
            raise UserNotFoundError("no account found for that email")
        if not user.is_active:
            raise AuthError("account disabled")

        now = int(time.time())
        claims = {
            "sub": user.id,
            "email": user.email,
            "roles": [user.role],  # Entra emits a `roles` array
            "agency_id": user.agency_id,
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    async def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as e:
            raise AuthError("session expired") from e
        except jwt.PyJWTError as e:
            raise AuthError("invalid token") from e

        principal = Principal.from_claims(claims)
        # Re-check account status on every request so deactivation takes effect immediately —
        # a still-valid token for a disabled/removed user is rejected. Service principals
        # (e.g. the AGENT/ingestion worker) aren't DB users, so they skip this check.
        if principal.role is not Role.AGENT:
            user = await self._users.get_by_id(principal.subject_id)
            if user is None:
                raise AuthError("account no longer exists")
            if not user.is_active:
                raise AuthError("account disabled")
        return principal


# Pre-computed argon2 hash of a random string, used only to equalize timing.
_DUMMY_HASH = _ph.hash("timing-equalizer")


__all__ = ["DbAuthProvider", "UserRecord", "UserRepository", "scope_for"]
