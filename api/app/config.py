"""Runtime configuration (SCOPING §9, §11). Secrets come from env, which in Azure are
projected from Key Vault via Managed Identity — never hard-coded.

The single switch that makes Entra a config flip is `AUTH_PROVIDER` (db | entra).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the default SQLite file to the repo root (this file is api/app/config.py), so the
# DB is the same single file no matter which directory the server/Alembic is launched from.
# A relative "./expense.db" would otherwise create a separate DB per working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SQLITE_URL = f"sqlite:///{(_REPO_ROOT / 'expense.db').as_posix()}"


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
    jwt_ttl_seconds: int = 3600
    entra_tenant_id: str = ""
    entra_audience: str = ""
    entra_jwks_url: str = ""

    # --- Data -------------------------------------------------------------- #
    # SQLite by default so the API runs with zero infra; point at Postgres in any real env.
    database_url: str = _DEFAULT_SQLITE_URL
    db_echo: bool = False

    # --- Seeding ----------------------------------------------------------- #
    seed_demo_data: bool = True  # seed agencies/users on startup in dev

    # --- Azure (optional; workers/engine use these when wired) ------------- #
    foundry_endpoint: str = ""
    foundry_chat_deployment: str = "gpt-4o"
    # Azure AI Document Intelligence — live receipt OCR/extraction for the scan endpoint.
    # Empty → offline fallback (decode text-based receipts only).
    doc_intel_endpoint: str = ""
    # Azure AI Search — RAG retrieval of the agency's policy clauses (advisory note).
    # Empty → no advisory (the deterministic policy check is unaffected).
    search_endpoint: str = ""
    search_index_name: str = "agency-policies"
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
