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

# Anchor the .env to the api/ dir (this file is api/app/config.py) so it loads no matter
# which directory uvicorn/pytest is launched from. A bare ".env" is resolved against the
# current working directory, which silently drops config when started from the repo root.
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=str(_ENV_FILE), extra="ignore"
    )

    environment: Literal["dev", "staging", "prod"] = "dev"

    # Browser origins allowed to call the API (the Next.js dev server / portal host).
    # Comma-separated; the frontend can't call the API cross-origin without this.
    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    # --- Auth -------------------------------------------------------------- #
    # db     → local email/password (DbAuthProvider, HS256).
    # entra  → Microsoft Entra ID (OIDC) — a preset of the generic `oidc` provider.
    # oidc   → any standard OIDC IdP (Entra/Google/Okta/Auth0/Ping/Keycloak) via config.
    # hybrid → BOTH at once: per-user `source` decides — "azure" users sign in via Entra,
    #          everyone else via local password. Bearer tokens verify by alg (HS=local, RS=Entra).
    auth_provider: Literal["db", "entra", "oidc", "hybrid"] = "db"
    jwt_secret: str = "dev-only-change-me"  # noqa: S105 — overridden via env/Key Vault
    jwt_algorithm: str = "HS256"
    # Access-token lifetime == the absolute session cap (8h). The client also enforces a
    # 30-min idle timeout, so an inactive session is logged out well before the token expires.
    jwt_ttl_seconds: int = 28800

    # Microsoft Entra ID (preset of the generic OIDC provider). Setting AUTH_PROVIDER=entra
    # derives the issuer from the tenant id; the rest reuse the OIDC_* knobs below.
    entra_tenant_id: str = ""
    entra_audience: str = ""
    entra_jwks_url: str = ""

    # --- Generic OIDC (federated identity, multi-provider) ----------------- #
    # Validation-only: the IdP runs the interactive Authorization-Code + PKCE flow (the
    # frontend/next-auth handles that); the API verifies the forwarded token against the
    # IdP's JWKS and resolves the app identity from our own users table (DB-by-email JIT).
    oidc_issuer: str = ""               # e.g. https://login.microsoftonline.com/<tenant>/v2.0
    oidc_audience: str = ""             # the API/app client id the token is minted for
    oidc_jwks_url: str = ""             # IdP JWKS endpoint (key rotation handled by PyJWKClient)
    oidc_algorithms: str = "RS256"      # comma-separated allowed signing algs
    oidc_email_claim: str = "email"     # claim holding the user's email (preferred_username fallback)
    oidc_subject_claim: str = "oid"     # stable IdP subject id (Entra: oid; others: sub)
    oidc_name_claim: str = "name"
    oidc_roles_claim: str = "roles"     # Entra app-roles arrive here
    oidc_groups_claim: str = "groups"   # group object-ids (when groups are emitted)
    # Configurable mapping of IdP app-role / group value → application role. JSON object,
    # e.g. {"Finance.Approver": "finance", "Super Admin": "admin", "<group-guid>": "manager"}.
    # Used as a fallback for role and for brand-new JIT users; DB role still wins for
    # existing users (DB-by-email is the source of truth, SCOPING ADR-001).
    oidc_role_map: str = "{}"
    # JIT provisioning: when a federated user has no matching DB account.
    #   false → deny with an administrator-approval message (default, safest).
    #   true  → auto-create the account using the mapped role + a default agency.
    oidc_auto_provision: bool = False
    oidc_default_role: str = "employee"     # role for auto-provisioned users with no mapping
    oidc_default_agency_id: str = ""        # agency for auto-provisioned users ("" → deny)

    # --- Email / password reset (local auth, SCOPING §3) ------------------- #
    # Backend that actually delivers mail. "console" logs the message (dev/offline, fully
    # testable with zero infra); "smtp" sends via the configured server (staging/prod).
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "no-reply@auxilab.local"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    # Base URL the reset link points at (the frontend portal origin).
    app_base_url: str = "http://localhost:3000"
    # Reset tokens are single-use and time-limited.
    reset_token_ttl_minutes: int = 30
    password_min_length: int = 10

    @property
    def oidc_algorithm_list(self) -> list[str]:
        return [a.strip() for a in self.oidc_algorithms.split(",") if a.strip()]

    # --- Data -------------------------------------------------------------- #
    # SQLite by default so the API runs with zero infra; point at Postgres in any real env.
    database_url: str = _DEFAULT_SQLITE_URL
    db_echo: bool = False

    # --- Seeding ----------------------------------------------------------- #
    seed_demo_data: bool = True  # seed agencies/users on startup in dev

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

    # Azure AI Document Intelligence (prebuilt-receipt) — empty endpoint → offline text parse.
    doc_intel_endpoint: str = ""
    doc_intel_api_key: str = ""  # prefer Managed Identity; key only for local dev

    # Microsoft Defender for Storage malware scanning (SCOPING §6.1). When True (default), a
    # receipt whose scan-result tag is ABSENT fails closed at intake; set False only in envs
    # where Defender isn't wired and you accept unscanned uploads. Offline (file:// blobs or no
    # storage account) the scan is a no-op so the local flow runs with zero infra.
    require_virus_scan: bool = True

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

    # --- SLA / aging escalation (SCOPING §6.4, §8) ------------------------ #
    # Hours a sheet may wait in a review queue before it's flagged. Mirrors the portal's
    # aging thresholds (frontend/src/lib/aging.ts): warning at 2 days, escalation at 5.
    escalation_warning_hours: int = 48
    escalation_critical_hours: int = 120

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
