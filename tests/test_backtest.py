"""Backtester — condor payoff at expiry and walk-forward metrics."""

import pytest

from paz_rav.backtest import pnl_at_expiry, run
from paz_rav.strategies import make_strategy


def condor():
    return make_strategy("iron_condor").build(
        underlying="SPY", spot=100.0, dte=45,
        put_long=90.0, put_short=95.0, call_short=105.0, call_long=110.0,
        credit=1.0, sigma=0.20,
    )


def test_pnl_between_shorts_is_full_credit():
    c = condor()
    assert pnl_at_expiry(c, 100.0) == pytest.approx(1.0)   # max profit
    assert pnl_at_expiry(c, 96.0) == pytest.approx(1.0)


def test_pnl_fully_breached_is_max_loss():
    c = condor()
    assert pnl_at_expiry(c, 80.0) == pytest.approx(-4.0)   # below long put
    assert pnl_at_expiry(c, 120.0) == pytest.approx(-4.0)  # above long call


def test_pnl_partial_breach():
    c = condor()
    # short put 95, credit 1 -> breakeven 94; at 93 the loss is 1.0
    assert pnl_at_expiry(c, 93.0) == pytest.approx(-1.0)


def test_walk_forward_metrics():
    c = condor()
    trades = [(c, 100.0), (c, 80.0), (c, 100.0)]   # win, loss, win
    res = run(trades)

    assert res.trades == 3
    assert res.wins == 2
    assert res.win_rate == pytest.approx(2 / 3, abs=1e-4)
    assert res.total_pnl == pytest.approx(1.0 - 4.0 + 1.0)
    assert res.equity_curve == [1.0, -3.0, -2.0]
    assert res.max_drawdown == pytest.approx(4.0)   # peak +1 to trough -3


def test_empty_backtest():
    res = run([])
    assert res.trades == 0 and res.total_pnl == 0.0
