"""ReasonFlow application settings.

Zero-config bootstrap guarantee (master prompt §5A): the app must start and
demonstrate the core product with no external credentials. Every optional
dependency degrades loudly (logged + reported by /health/ready), never crashes.
"""
from __future__ import annotations

import os
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---------------------------------------------------------------
    app_name: str = "ReasonFlow"
    env: str = "local"  # local | docker | test
    api_prefix: str = "/api/v1"
    # PostgreSQL 16+ is the canonical store (docker-compose wires pgvector:pg16).
    # SQLite remains ONLY as an explicit offline fallback (set DATABASE_URL yourself
    # or run with no Postgres reachable) — loudly labeled DEGRADED at boot.
    database_url: str = "postgresql+psycopg://reasonflow:reasonflow@localhost:5432/reasonflow"
    redis_url: str | None = None  # absent => in-process fallbacks, logged degraded

    # --- Security -----------------------------------------------------------
    secret_key: str = ""  # generated for dev if empty; production MUST set it
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    pbkdf2_iterations: int = 210_000
    login_max_failures: int = 5
    login_rate_per_minute: int = 10  # per email+ip in-process limiter (S6: Redis-backed)
    login_lockout_minutes: int = 15
    demo_mode: bool = True

    # --- AI governance (optional; absent => deterministic mode, S10 wires the gateway) ---
    openai_api_key: str | None = None
    embedding_api_key: str | None = None
    llm_enabled_default: bool = True  # still falls back when no provider key exists
    daily_cost_cap_rs: float = 100.0

    # --- App lifecycle ------------------------------------------------------
    seed_on_boot: bool = True

    _cached_fallback_secret: str | None = None

    def effective_secret_key(self) -> str:
        if self.secret_key:
            return self.secret_key
        if self.env in ("local", "test"):
            # Deterministic-per-boot dev key is acceptable only outside production.
            return "reasonflow-dev-secret-key-do-not-use-in-production"
        if not hasattr(self, "_cached_fallback_secret") or not self._cached_fallback_secret:
            object.__setattr__(self, "_cached_fallback_secret", secrets.token_urlsafe(48))
        return self._cached_fallback_secret

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

settings = Settings()
