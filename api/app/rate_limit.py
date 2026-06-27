"""Per-IP rate limiting (slowapi) for the pre-auth surface (security: S-H1).

A single shared `Limiter` keyed on the client IP. Disabled in tests (and any env that sets
`APP_RATE_LIMIT_ENABLED=false`) so suites can hammer `/auth` freely. In-memory storage is fine
for a single instance; point slowapi at Redis for multi-instance deployments.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
