"""Runtime configuration (SCOPING §9, §11). Secrets come from env, which in Azure are
projected from Key Vault via Managed Identity — never hard-coded.

The single switch that makes Entra a config flip is `AUTH_PROVIDER` (db | entra).
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    environment: Literal["dev", "staging", "prod"] = "dev"

    # --- Auth -------------------------------------------------------------- #
    auth_provider: Literal["db", "entra"] = "db"
    jwt_secret: str = "dev-only-change-me"  # noqa: S105 — overridden via env/Key Vault
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 3600
    entra_tenant_id: str = ""
    entra_audience: str = ""
    entra_jwks_url: str = ""

    # --- Data -------------------------------------------------------------- #
    # SQLite by default so the API runs with zero infra; point at Postgres in any real env.
    database_url: str = "sqlite:///./expense.db"
    db_echo: bool = False

    # --- Seeding ----------------------------------------------------------- #
    seed_demo_data: bool = True  # seed agencies/users on startup in dev

    # --- Azure (optional; workers/engine use these when wired) ------------- #
    foundry_endpoint: str = ""
    foundry_chat_deployment: str = "gpt-4o"
    storage_account_url: str = ""
    servicebus_namespace: str = ""

    # --- Agency policy documents (RAG ingestion, SCOPING §7) --------------- #
    # Blob container for uploaded policy docs. With no storage_account_url configured the
    # API falls back to a local directory so the whole flow runs offline (zero infra).
    policy_container: str = "agency-policies"
    policy_local_dir: str = "./policy_uploads"  # offline fallback store
    ingestion_queue_name: str = "document-ingestion"  # Service Bus queue the worker reads

    # --- Receipt uploads (per-line-item, SCOPING §4.2) -------------------- #
    # Stored under receipts/{employee_id}/<file>. Offline falls back to a local directory.
    receipt_container: str = "receipts"
    receipt_local_dir: str = "./receipt_uploads"  # offline fallback store

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
