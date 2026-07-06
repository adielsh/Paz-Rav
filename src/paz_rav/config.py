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
    # SPX first (primary iron-condor name) + ETFs + big single names.
    underlyings: str = "SPX,SPY,QQQ,IWM,NVDA,MSFT,GOOGL,AMZN,CSCO"
    agent_concurrency: int = 4
    # data source: "yfinance" (live, free, delayed) or "fixture" (offline, always works)
    paz_data: str = "yfinance"

    # ---- strategy tuning (override via env, e.g. PAZ_DACS_MIN_FAST_RATIO=0.15) ----
    # Volatility risk premium: options are priced ~15% above what realizes, which is the
    # documented edge premium-sellers harvest. Set 0 to price at fair value.
    vrp: float = 0.15
    condor_target_dte: int = 35        # iron condor front DTE (1-2 wks .. 45d)
    dacs_short_dte: int = 35           # sell ~1 month out
    dacs_gap_days: int = 30            # buy ~1 month beyond the short
    dacs_otm: float = 0.10             # short call ~10% OTM
    dacs_max_delta: float = 0.20       # short delta cap
    dacs_min_long_price: float = 1.0   # long option worth > $1
    dacs_min_fast_ratio: float = 0.12  # long value / risk floor

    @property
    def underlying_list(self) -> list[str]:
        return [u.strip().upper() for u in self.underlyings.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
