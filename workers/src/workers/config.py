"""Worker configuration (SCOPING §6.4, §11, §13, §14).

pydantic-settings with the `WORKERS_` env prefix. Every value has an offline-safe
default so the package imports and the `demo`/tests run with no environment set; the
Azure-backed implementations only read their endpoints when explicitly constructed.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the finance-approver worker and consumers.

    Offline defaults select the in-memory fallbacks; populate the Azure fields (via
    env or `.env`) and install the `[azure]` extra to wire real services.
    """

    model_config = SettingsConfigDict(
        env_prefix="WORKERS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service Bus (async finance-approval + ingestion queues, SCOPING §11, §14) ---
    service_bus_connection_string: str = ""  # empty → offline; no real consumer
    finance_queue_name: str = "finance-approval"
    ingestion_queue_name: str = "document-ingestion"
    max_delivery_count: int = 5  # dead-letter after N retries; never silent-approve
    receive_max_wait_seconds: int = 30

    # --- Azure AI Search (per-agency RAG index, SCOPING §7) ---
    search_endpoint: str = ""  # empty → InMemoryRetriever
    search_index_name: str = "agency-policies"
    search_api_key: str = ""  # prefer Managed Identity; key only for local dev

    # --- Azure AI Foundry (model-agnostic LLM gateway, SCOPING §11) ---
    foundry_endpoint: str = ""  # empty → LocalEchoProvider
    foundry_deployment: str = "gpt-4o-mini"
    embedding_deployment: str = "text-embedding-3-large"  # ingestion embeds with this

    # --- Document ingestion: Blob + Document Intelligence (SCOPING §7) ---
    storage_account_url: str = ""  # empty → offline: read file:// blob URIs locally
    doc_intel_endpoint: str = ""  # empty → offline: read text blobs as-is

    # --- Ingestion → API callback (stamps AgencyPolicy.indexed_at, SCOPING §7) ---
    api_base_url: str = ""  # empty → no callback (offline)
    agent_token: str = ""  # AGENT bearer for POST /finance/policies/{id}/indexed

    # --- Azure AI Content Safety / Prompt Shields (SCOPING §7, §9.2) ---
    content_safety_endpoint: str = ""  # empty → NoopShield
    content_safety_api_key: str = ""

    # --- LLM guardrails (SCOPING §6.4, §9.2) ---
    confidence_routing_threshold: float = 0.7  # below → route to human
    per_sheet_token_budget: int = 20_000  # cost ceiling for large sheets (SCOPING §8)
    llm_temperature: float = 0.0  # low temperature for reproducibility

    @property
    def azure_search_enabled(self) -> bool:
        return bool(self.search_endpoint)

    @property
    def azure_foundry_enabled(self) -> bool:
        return bool(self.foundry_endpoint)

    @property
    def content_safety_enabled(self) -> bool:
        return bool(self.content_safety_endpoint)

    @property
    def service_bus_enabled(self) -> bool:
        return bool(self.service_bus_connection_string)


def load_settings() -> Settings:
    """Load settings from env / `.env`, falling back to offline defaults."""
    return Settings()
