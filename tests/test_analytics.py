"""Analytics feature engine — IV solving, IV rank, regime, and end-to-end analyze()."""

import math
from datetime import date, datetime, timezone

import pytest

from paz_rav.analytics import analyze, classify, iv_percentile, iv_rank
from paz_rav.analytics.regime import condor_friendly, trend_state
from paz_rav.contracts import OptionQuote
from paz_rav.quant import black_scholes, implied_vol

TODAY = date(2026, 1, 15)


def make_chain(expiry: date, vol: float, strikes=(90, 95, 100, 105, 110)) -> list[OptionQuote]:
    ts = datetime(2026, 1, 15, tzinfo=timezone.utc)
    quotes = []
    for k in strikes:
        for right in ("call", "put"):
            quotes.append(OptionQuote(
                underlying="TST", right=right, strike=float(k), expiry=expiry,
                bid=1.0, ask=1.1, implied_vol=vol, ts=ts,
            ))
    return quotes


def test_implied_vol_round_trip():
    price = black_scholes(100, 100, 0.5, 0.04, 0.23, "call")
    assert implied_vol(price, 100, 100, 0.5, 0.04, "call") == pytest.approx(0.23, abs=1e-4)


def test_iv_rank_and_percentile():
    hist = [0.10, 0.15, 0.20, 0.25, 0.30]
    assert iv_rank(0.20, hist) == pytest.approx(50.0)
    assert iv_rank(0.30, hist) == pytest.approx(100.0)
    assert iv_rank(0.10, hist) == pytest.approx(0.0)
    assert iv_rank(0.20, []) == 50.0            # unknown → neutral
    assert iv_percentile(0.26, hist) == pytest.approx(80.0)


def test_regime_classification():
    # spot well above its recent mean → uptrend; high IV rank → high vol
    assert trend_state(110, [100, 100, 100]) == "trend-up"
    assert trend_state(90, [100, 100, 100]) == "trend-down"
    assert trend_state(100, [100, 100, 100]) == "range"
    assert classify(70.0, 100, [100, 100, 100]) == "range / high-vol"
    assert condor_friendly("range / high-vol") is True
    assert condor_friendly("trend-up / low-vol") is False


def test_analyze_end_to_end():
    front = date(2026, 3, 1)   # 45 DTE from TODAY
    back = date(2026, 3, 31)   # ~75 DTE
    chains = {front: make_chain(front, 0.20), back: make_chain(back, 0.24)}

    res = analyze(
        "TST", spot=100.0, chains_by_expiry=chains,
        iv_history=[0.10, 0.15, 0.20, 0.25, 0.30],   # atm 0.20 → rank 50
        price_history=[95, 96, 97],                   # spot 100 above mean → uptrend
        today=TODAY,
    )
    f = res.feature
    assert f.underlying == "TST"
    assert f.spot == 100.0
    assert res.atm_iv == pytest.approx(0.20, abs=1e-6)

    t_front = (front - TODAY).days / 365.0
    assert f.expected_move == pytest.approx(100 * 0.20 * math.sqrt(t_front), abs=1e-3)

    assert f.iv_rank == pytest.approx(50.0)
    assert f.term_slope > 0.0                          # back-month IV richer than front
    assert f.regime == "trend-up / high-vol"
    assert set(res.per_expiry_iv) == {front.isoformat(), back.isoformat()}
