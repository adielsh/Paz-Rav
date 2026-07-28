"""Unit tests for pure logic — no IB connection or DB server required."""
import datetime as dt

import pytest

from app.config import CONFIG
from app.utils import round_to_tick, tick_for, valid, nan_safe, dte_of, is_trading_day, is_entry_time_open
from app import db


# ---- tick rounding (CBOE: 0.05 <3.00, 0.10 >=3.00) --------------------------------------
# Note: exact half-tick inputs (e.g. 5.05 at a 0.10 tick) are float-ambiguous and round to even
# (banker's rounding, matching the examine.py reference). We don't assert those boundary cases.
@pytest.mark.parametrize("raw,expected", [
    (1.23, 1.25), (1.22, 1.20), (2.99, 3.00), (3.14, 3.10), (3.16, 3.20),
    (0.07, 0.05), (-1.24, -1.25), (5.04, 5.00), (5.06, 5.10),
])
def test_round_to_tick(raw, expected):
    assert round_to_tick(raw) == pytest.approx(expected)


def test_tick_for_boundary():
    assert tick_for(2.99) == 0.05
    assert tick_for(3.00) == 0.10


# ---- NaN helpers ------------------------------------------------------------------------
def test_valid_and_nan_safe():
    assert valid(1.0) and not valid(float("nan")) and not valid(None)
    assert nan_safe(None) != nan_safe(None)  # NaN != NaN
    assert nan_safe(2.5) == 2.5


# ---- VIX delta state machine ------------------------------------------------------------
def test_vix_delta_bands():
    assert CONFIG.target_deltas(13.99) == (0.15, 0.15)
    assert CONFIG.target_deltas(14.0) == (0.30, 0.20)
    assert CONFIG.target_deltas(22.0) == (0.30, 0.20)
    assert CONFIG.target_deltas(22.01) is None


# ---- DTE + calendar ---------------------------------------------------------------------
def test_dte_of():
    ref = dt.date(2026, 7, 26)
    assert dte_of("20260904", ref=ref) == 40


def test_calendar_weekend_and_weekday():
    assert is_trading_day(dt.date(2026, 7, 27)) is True     # Monday
    assert is_trading_day(dt.date(2026, 7, 26)) is False    # Sunday
    assert is_entry_time_open(dt.date(2026, 7, 27)) is True
    assert is_entry_time_open(dt.date(2026, 7, 26)) is False


# ---- DB schema round-trip on SQLite -----------------------------------------------------
def test_db_roundtrip_and_control():
    S = db.init_db("sqlite+pysqlite:///:memory:")
    assert db.trading_enabled() is True
    with S() as s:
        t = db.Trade(expiry="20260904", dte=40, vix_avg=15.2,
                     put_short_strike=6200, put_long_strike=6150,
                     call_short_strike=6500, call_long_strike=6550,
                     target_put_delta=0.30, target_call_delta=0.20,
                     entry_credit=1.35, quantity=1, leg_conids=[1, 2, 3, 4])
        s.add(t); s.flush()
        s.add(db.Fill(trade_id=t.id, kind="entry", price=1.35, quantity=1))
        s.add(db.GateDecision(vix=15.2, accepted=True, reason="ok", details={"credit": 1.35}))
        s.commit()
        assert t.id == 1
        assert len(t.fills) == 1
