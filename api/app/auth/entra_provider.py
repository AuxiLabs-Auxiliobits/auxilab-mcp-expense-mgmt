"""EntraAuthProvider — LATER. Validation-only: Entra hosts login and mints the token;
we verify it against Entra's JWKS and map its claims to our Principal.

Flipping APP_AUTH_PROVIDER=entra activates this. No other app code changes (ADR-001).
"""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from app.auth.base import AuthError, AuthProvider
from app.principal import Principal, Role


class EntraAuthProvider(AuthProvider):
    def __init__(self, tenant_id: str, audience: str, jwks_url: str):
        self._issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self._audience = audience
        self._jwks = PyJWKClient(jwks_url)

    async def authenticate(self, email: str, password: str) -> str:
        # Login is Entra's job (social IdP / SSO / MFA). We never see the password.
        raise AuthError("login is handled by Entra; use the hosted sign-in flow")

    async def verify(self, token: str) -> Principal:
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as e:
            raise AuthError("invalid token") from e

        # Map Entra app-role/group claims → our Role enum. App roles arrive in `roles`.
        claims.setdefault("sub", claims.get("oid", ""))
        roles = [r for r in claims.get("roles", []) if r in Role._value2member_map_]
        if not roles:
            raise AuthError("no recognized app role in token")
        claims["roles"] = roles
        return Principal.from_claims(claims)
