"""
ExpenseOps Configuration Module
================================
Uses pydantic-settings to load configuration from environment variables
and a .env file. All sensitive keys and runtime toggles live here.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object.
    Values are loaded in this priority order:
      1. Environment variables (highest)
      2. .env file
      3. Default values defined here (lowest)
    """

    # ── Database ────────────────────────────────────────────────────────
    # SQLite by default; swap to PostgreSQL/MySQL via DATABASE_URL env var.
    DATABASE_URL: str = "sqlite:///./data/expenseops_v2.db"
    SUPABASE_URL: str = ""

    # ── AI / LLM Provider ──────────────────────────────────────────────
    # "mock" uses rule-based stubs so the app works without any API keys.
    # Set to "openai" or "anthropic" to enable real LLM calls.
    AI_PROVIDER: str = "mock"

    # Optional API keys – only required when AI_PROVIDER != "mock"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    XAI_API_KEY: str = ""

    # ── Policy / Exception file paths ──────────────────────────────────
    POLICY_FILE_PATH: str = "policies/policy_rules.json"
    EXCEPTIONS_FILE_PATH: str = "policies/exceptions.json"

    # ── Security ────────────────────────────────────────────────────────
    EXECUTIVE_MASTER_KEY: str = "ExpenseOps123"
    SECRET_KEY: str = "expenseops-super-secret-key-1234"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 1 week

    # pydantic-settings v2 configuration via model_config
    model_config = SettingsConfigDict(
        env_file=".env",          # look for a .env in the working directory
        env_file_encoding="utf-8",
        case_sensitive=True,      # DATABASE_URL != database_url
        extra="ignore",           # silently ignore unknown env vars
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.
    Using lru_cache means the .env file is read exactly once per process.
    """
    return Settings()
