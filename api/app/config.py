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
    # db    → local email/password (DbAuthProvider, HS256).
    # entra → Microsoft Entra ID (OIDC) — a preset of the generic `oidc` provider.
    # oidc  → any standard OIDC IdP (Entra/Google/Okta/Auth0/Ping/Keycloak) via config.
    auth_provider: Literal["db", "entra", "oidc"] = "db"
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
    database_url: str = "sqlite:///./expense.db"
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
