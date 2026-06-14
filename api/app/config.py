"""Runtime configuration. The single switch that makes Entra a config flip is
`AUTH_PROVIDER` (db | entra). Secrets come from Key Vault via env in real envs."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    auth_provider: Literal["db", "entra"] = "db"

    # DbAuthProvider — symmetric signing for our own tokens.
    jwt_secret: str = "dev-only-change-me"  # noqa: S105 — overridden via env/Key Vault
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 3600

    # EntraAuthProvider — validation only; we never mint Entra tokens.
    entra_tenant_id: str = ""
    entra_audience: str = ""  # api://<app-id>
    entra_jwks_url: str = ""  # https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys

    database_url: str = "postgresql://localhost:5432/expense"


settings = Settings()
