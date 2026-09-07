"""Central configuration for the SPX Iron Condor trading-core.

All operational parameters live here. Runtime/secret values (IB host/port, DB DSN) come from
environment variables so the same image runs in Docker and on the host. Strategy parameters are
constants — deliberately explicit and auditable.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Config:
    # ---- IB connection (env-overridable) -------------------------------------------------
    ib_host: str = field(default_factory=lambda: _env("IB_HOST", "127.0.0.1"))
    ib_port: int = field(default_factory=lambda: int(_env("IB_PORT", "4002")))
    ib_client_id: int = field(default_factory=lambda: int(_env("IB_CLIENT_ID", "11")))
    # Require a paper account (id starts with this) unless explicitly cleared for go-live.
    paper_account_prefix: str = field(default_factory=lambda: _env("PAPER_ACCOUNT_PREFIX", "DU"))
    # IBKR market data type: 1=live, 2=frozen, 3=delayed, 4=delayed-frozen.
    # This account has no live index/option subscription, so requests return nothing at all
    # unless delayed is asked for explicitly. NOTE: delayed quotes lag ~15 minutes — fine for
    # building/validating the pipeline, NOT sound for pricing a real entry.
    market_data_type: int = field(default_factory=lambda: int(_env("MARKET_DATA_TYPE", "3")))

    # ---- Database ------------------------------------------------------------------------
    db_dsn: str = field(default_factory=lambda: _env(
        "DB_DSN", "postgresql+psycopg://condor:condor@127.0.0.1:5432/condor"))

    # ---- Instrument ----------------------------------------------------------------------
    symbol: str = "SPX"
    trading_class: str = "SPXW"      # PM-settled weeklies only
    exchange: str = "CBOE"
    multiplier: int = 100
    lot_size: int = 1                # fixed 1-lot (confirmed decision)

    # ---- Schedule ------------------------------------------------------------------------
    timezone: str = "America/New_York"
    entry_hour: int = 14
    entry_minute: int = 30

    # ---- Structure -----------------------------------------------------------------------
    dte_min: int = 35
    dte_max: int = 45
    dte_target: int = 40
    wing_width: int = 50
    gamma_stop_dte: int = 25

    # ---- VIX delta state machine ---------------------------------------------------------
    # (vix_upper_bound, put_delta, call_delta); scanned in order. None target => suspend.
    vix_low_ceiling: float = 14.0
    vix_high_ceiling: float = 22.0
    delta_low: tuple = (0.15, 0.15)   # VIX < 14
    delta_mid: tuple = (0.30, 0.20)   # 14 <= VIX <= 22 (intentional put-skew)

    # ---- Pre-flight gates ----------------------------------------------------------------
    min_credit: float = 1.20
    max_spread: float = 1.50
    margin_nlv_fraction: float = 0.70
    tp_credit_delta: float = 0.50     # buy back 0.50 cheaper => $50 profit / lot

    # ---- Execution -----------------------------------------------------------------------
    entry_tick_step_seconds: int = 10
    entry_ttl_seconds: int = 120

    # ---- Manual approval -----------------------------------------------------------------
    # When on (the default), a passing entry is parked as a proposal for a human to approve
    # in the UI instead of being transmitted. Set REQUIRE_APPROVAL=0 for fully automatic entry.
    require_approval: bool = field(
        default_factory=lambda: _env("REQUIRE_APPROVAL", "1") == "1")
    # How long a pending proposal stays actionable before it self-expires.
    proposal_ttl_minutes: int = field(
        default_factory=lambda: int(_env("PROPOSAL_TTL_MINUTES", "120")))

    def target_deltas(self, vix: float):
        """Return (put_delta, call_delta) for the VIX regime, or None to suspend."""
        if vix < self.vix_low_ceiling:
            return self.delta_low
        if vix <= self.vix_high_ceiling:
            return self.delta_mid
        return None  # VIX > 22 -> systemic volatility alert, suspend


CONFIG = Config()
