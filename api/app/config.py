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

    # Browser origins allowed to call the API (the Next.js dev server / portal host).
    # Comma-separated; the frontend can't call the API cross-origin without this.
    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    # --- Auth -------------------------------------------------------------- #
    auth_provider: Literal["db", "entra"] = "db"
    jwt_secret: str = "dev-only-change-me"  # noqa: S105 — overridden via env/Key Vault
    jwt_algorithm: str = "HS256"
    # Access-token lifetime == the absolute session cap (8h). The client also enforces a
    # 30-min idle timeout, so an inactive session is logged out well before the token expires.
    jwt_ttl_seconds: int = 28800
    entra_tenant_id: str = ""
    entra_audience: str = ""
    entra_jwks_url: str = ""

    # --- Data -------------------------------------------------------------- #
    # SQLite by default so the API runs with zero infra; point at Postgres in any real env.
    database_url: str = "sqlite:///./expense.db"
    db_echo: bool = False

    # --- Seeding ----------------------------------------------------------- #
    seed_demo_data: bool = True  # seed agencies/users on startup in dev

    # --- Agentic layer ----------------------------------------------------- #
    # Fire AI recommendation/notification events from lifecycle endpoints (background tasks).
    # Disabled in the test harness, where in-process background writes contend on SQLite; the
    # event handler is exercised directly there instead.
    ai_background_events: bool = True

    # --- Azure (optional; workers/engine use these when wired) ------------- #
    # Azure AI Foundry (chat) — empty endpoint → offline deterministic answers.
    foundry_endpoint: str = ""
    foundry_chat_deployment: str = "gpt-4o"
    foundry_api_key: str = ""  # prefer Managed Identity; key only for local dev
    foundry_api_version: str = "2024-10-21"
    # Azure AI Search (per-agency policy RAG index) — empty → offline retrieval from the
    # agency's stored policy doc / baseline ruleset.
    search_endpoint: str = ""
    search_index_name: str = "agency-policies"
    search_api_key: str = ""  # prefer Managed Identity; key only for local dev
    search_semantic_config: str = "default"  # must match the index's semantic configuration
    storage_account_url: str = ""
    servicebus_namespace: str = ""

    @property
    def azure_foundry_enabled(self) -> bool:
        return bool(self.foundry_endpoint)

    @property
    def azure_search_enabled(self) -> bool:
        return bool(self.search_endpoint)

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
