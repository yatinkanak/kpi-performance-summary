"""Centralized configuration, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Well-known dev placeholder. Fine for local/docker; rejected when running in production.
DEV_PUBLISH_TOKEN = "dev-publish-token"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KPS_", env_file=".env", extra="ignore")

    # Deployment environment. Stays "development" unless KPS_ENVIRONMENT=production is set,
    # which flips on the production guards below.
    environment: str = "development"

    # Async SQLAlchemy URL (asyncpg driver).
    database_url: str = "postgresql+asyncpg://kps:kps@localhost:5432/kps"

    # --- Database connection pool (SQLAlchemy QueuePool) ---
    # Tunable per environment so a multi-worker deploy can size the pool to its DB limits.
    db_pool_size: int = Field(10, ge=1)  # persistent connections kept open
    db_max_overflow: int = Field(20, ge=0)  # extra connections allowed under load burst
    db_pool_timeout: int = Field(30, ge=1)  # seconds to wait for a free connection
    db_pool_recycle: int = Field(1800, ge=-1)  # recycle connections older than N sec (-1 = never)
    db_pool_pre_ping: bool = True  # liveness-check a connection before use

    # Token gating the single write path. Defaults to a dev placeholder so the app runs
    # out of the box; in production the placeholder is rejected (see the validator) so a
    # real deploy can't silently ship with a publicly-known token.
    publish_token: str = DEV_PUBLISH_TOKEN

    # Comma-separated CORS allowlist for the browser SPA.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Pagination guardrail.
    max_page_size: int = 200

    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @model_validator(mode="after")
    def _reject_dev_token_in_production(self) -> Settings:
        """Fail closed in production rather than ship the publicly-known dev token."""
        if self.is_production and self.publish_token == DEV_PUBLISH_TOKEN:
            raise ValueError(
                "KPS_PUBLISH_TOKEN must be set to a strong, non-default value when "
                "KPS_ENVIRONMENT=production."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
