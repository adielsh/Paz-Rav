"""Runtime configuration, loaded from environment / .env.

One typed settings object the whole process shares. See ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # vendor
    polygon_api_key: str = ""

    # datastores
    database_url: str = "postgresql://paz:paz@localhost:5432/pazrav"
    redis_url: str = "redis://localhost:6379/0"

    # ai layer (Phase 2)
    anthropic_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # runtime
    paz_env: str = "local"
    log_level: str = "INFO"
    underlyings: str = "SPY,QQQ,IWM,SPX,RUT"
    agent_concurrency: int = 4

    @property
    def underlying_list(self) -> list[str]:
        return [u.strip().upper() for u in self.underlyings.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
