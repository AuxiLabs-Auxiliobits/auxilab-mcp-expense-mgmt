"""HybridAuthProvider — local password auth AND Entra OIDC in one provider.

Per-user `source` decides the login path:
  • source == "azure"        → no local password; the user signs in at Entra (so a
                               password attempt here is rejected with a clear message).
  • source "manual" / None   → local email + password via DbAuthProvider (HS256 JWT).

Bearer-token verification dispatches by the token's signing algorithm:
  • HS*  → our own local JWT  → DbAuthProvider.verify
  • RS*  → an Entra ID token  → OidcAuthProvider.verify (JWKS-validated)

This lets manual and Azure users coexist behind the same API without a config flip.
"""

from __future__ import annotations

import jwt
from sqlmodel import Session, select

from app.auth.base import AuthError, AuthProvider
from app.auth.db_provider import DbAuthProvider
from app.auth.oidc_provider import OidcAuthProvider
from app.models.user import User
from app.principal import Principal


class HybridAuthProvider(AuthProvider):
    def __init__(self, db: DbAuthProvider, oidc: OidcAuthProvider, session: Session) -> None:
        self._db = db
        self._oidc = oidc
        self._session = session

    async def authenticate(self, email: str, password: str) -> str:
        # Azure accounts have no local password — force them through SSO.
        user = self._session.exec(
            select(User).where(User.email == email.strip().lower())
        ).first()
        if user is not None and (user.source or "").lower() == "azure":
            raise AuthError(
                "This account uses Microsoft sign-in. Please use 'Continue with Microsoft'."
            )
        return await self._db.authenticate(email, password)

    async def verify(self, token: str) -> Principal:
        try:
            alg = str(jwt.get_unverified_header(token).get("alg", ""))
        except jwt.PyJWTError as e:
            raise AuthError("invalid token") from e
        # Our local tokens are HMAC (HS256); Entra ID tokens are RSA (RS256).
        if alg.upper().startswith("HS"):
            return await self._db.verify(token)
        return await self._oidc.verify(token)
