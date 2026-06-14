"""The auth seam. App code depends on AuthProvider, not on Entra or our DB.

Swapping issuers = swapping the concrete class behind this interface (config flip).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.principal import Principal


class AuthError(Exception):
    """Raised on any authentication failure (bad creds, invalid/expired token)."""


class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, email: str, password: str) -> str:
        """Verify credentials and return a signed JWT.

        EntraAuthProvider does NOT implement this — login happens at Entra's
        hosted endpoint, not here; it raises AuthError to make that explicit.
        """

    @abstractmethod
    async def verify(self, token: str) -> Principal:
        """Validate a bearer token and return the normalized Principal."""
