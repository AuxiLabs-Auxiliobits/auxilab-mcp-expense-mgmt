"""Liveness/readiness (SCOPING §14 observability)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe (no auth)")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment, "auth": settings.auth_provider}
