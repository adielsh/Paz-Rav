"""Pure helpers: tick rounding, NaN handling, ET clock, market-calendar checks.

These are deliberately dependency-light and unit-testable without an IB connection.
"""
from __future__ import annotations

import math
from datetime import datetime, date

import pytz
import pandas_market_calendars as mcal

from .config import CONFIG

_ET = pytz.timezone(CONFIG.timezone)
_CBOE = mcal.get_calendar("CBOE_Index_Options")  # SPX/SPXW trading calendar


# ---- numeric helpers --------------------------------------------------------------------
def round_to_tick(price: float) -> float:
    """CBOE option tick: 0.05 below 3.00, 0.10 at/above 3.00. Sign-preserving."""
    tick = 0.05 if abs(price) < 3.00 else 0.10
    return round(round(price / tick) * tick, 2)


def tick_for(price: float) -> float:
    return 0.05 if abs(price) < 3.00 else 0.10


def valid(x) -> bool:
    """True if x is a real, non-NaN number."""
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def nan_safe(x) -> float:
    return x if valid(x) else float("nan")


# ---- clock / calendar -------------------------------------------------------------------
def now_et() -> datetime:
    return datetime.now(_ET)


def to_et(dt: datetime) -> datetime:
    return dt.astimezone(_ET)


def dte_of(expiry: str, ref: date | None = None) -> int:
    """Calendar days to an SPXW expiry (YYYYMMDD), measured from today's ET date."""
    exp = datetime.strptime(expiry, "%Y%m%d").date()
    ref = ref or now_et().date()
    return (exp - ref).days


def is_trading_day(d: date | None = None) -> bool:
    """True if d is a full US options trading day (not a holiday)."""
    d = d or now_et().date()
    sched = _CBOE.schedule(start_date=d.isoformat(), end_date=d.isoformat())
    return not sched.empty


def is_entry_time_open(d: date | None = None) -> bool:
    """True if the market is open through the configured 14:30 ET entry time (skips early-close)."""
    d = d or now_et().date()
    sched = _CBOE.schedule(start_date=d.isoformat(), end_date=d.isoformat())
    if sched.empty:
        return False
    close_et = to_et(sched.iloc[0]["market_close"].to_pydatetime())
    entry = _ET.localize(datetime(d.year, d.month, d.day, CONFIG.entry_hour, CONFIG.entry_minute))
    return entry < close_et
