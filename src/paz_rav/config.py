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

    # ---- advisor microservice (optional extraction of the close-timing debate) ----
    # Empty -> the monolith runs the Analyst/Critic/Decider debate in-process (default).
    # Set e.g. http://advisor:8001 to offload the (slow, LLM-bound) debate to a separate
    # deployable that scales on its own; the monolith calls it over HTTP and falls back to
    # the in-process debate if it's unreachable (a small circuit breaker). See
    # paz_rav/services/advisor/app.py.
    advisor_url: str = ""
    advisor_timeout: float = 30.0

    # runtime
    paz_env: str = "local"
    log_level: str = "INFO"
    # SPX first (primary iron-condor name) + ETFs + big single names.
    underlyings: str = "SPX,SPY,QQQ,IWM,NVDA,MSFT,GOOGL,AMZN,CSCO"
    agent_concurrency: int = 4
    # data source: "yfinance" (free, delayed), "ibkr" (the same gateway the console's
    # daemon trades through) or "fixture" (offline, always works)
    paz_data: str = "yfinance"

    # ---- IBKR feed (only read when paz_data == "ibkr") ----
    # Inside compose the gateway is reachable at ib-gateway:4004 (its socat port); from
    # the host it is 127.0.0.1:4002.
    ib_host: str = "127.0.0.1"
    ib_port: int = 4002
    # MUST NOT collide with the console: its daemon holds clientId 11 and its API rotates
    # through 12-23. A repeated clientId makes the gateway hang the handshake.
    ib_client_id: int = 25
    # 1 = live, 3 = delayed. Delayed is the default because an account without an option
    # data subscription returns EMPTY quotes on type 1 rather than an error.
    ib_market_data_type: int = 3
    # Concurrent market-data lines. IBKR caps ~100 per login and the trading daemon shares
    # that cap; exceeding it returns nothing silently rather than raising, so this stays
    # deliberately low. Raising it risks starving the service that actually places orders.
    ib_max_lines: int = 32
    # Strikes are taken from a +-`ib_moneyness` band around spot, thinned evenly to at
    # most `ib_strikes_each_side` per side. The band gives reach (a 16-delta short strike
    # at 35 DTE is nowhere near spot); the cap keeps a $1 ladder from blowing the budget.
    ib_strikes_each_side: int = 18
    ib_moneyness: float = 0.12
    ib_quote_timeout: float = 6.0
    # Seconds between full scans of the universe. 60 is fine for yfinance, which answers
    # a whole chain in one HTTP call. It is NOT enough for the IBKR feed: that quotes
    # contract by contract under a line budget, so one underlying takes ~15-20s and nine
    # of them overrun the interval. Raise this when PAZ_DATA=ibkr.
    scan_interval: float = 60.0
    # storage: "memory" (default, nothing survives a restart) or "redis_postgres"
    # (real persistence — features/IV-history/bus on Redis, candidates on Postgres;
    # needs `docker compose up -d` running first).
    paz_persist: str = "memory"
    # How long a scanned candidate stays queryable, in days. The scanner writes roughly
    # 60k rows/day (9 underlyings × ~10 candidates, every 60s) and nothing but `latest()`
    # ever reads them, so without a ceiling the table grows without bound — in the same
    # database that holds real trading data. 0 disables pruning entirely.
    candidate_retention_days: int = 7

    # ---- auth (public deployment) ----
    # Firebase Google Sign-In verification. Empty allowed_email -> auth is OFF (local/dev
    # default: don't lock the user out of their own app). Set both to gate the app behind
    # Google Sign-In when exposed publicly. allowed_email is also the owner: any OTHER
    # email that signs in goes through the access_requests approval flow instead of
    # being let in directly.
    firebase_project_id: str = ""
    allowed_email: str = ""

    # ---- access-request notifications (optional; only needed for the approval flow) ----
    # Gmail SMTP + an App Password (not your real password) — free, no new external
    # service. Empty gmail_app_password -> notifications are skipped (the request is
    # still recorded; you'd just need to check the pending list some other way).
    gmail_address: str = ""
    gmail_app_password: str = ""
    # Base URL the approval email links to, e.g. https://random-words.trycloudflare.com
    # (a Cloudflare Quick Tunnel URL changes on restart — update this when it does).
    public_base_url: str = ""

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
