"""Strategy factory + iron condor construction (grid-scored)."""

import pytest

from paz_rav.strategies import (
    Diagonal,
    DoubleDiagonal,
    IronCondor,
    list_strategies,
    make_strategy,
)


def test_factory_registers_strategies():
    assert isinstance(make_strategy("iron_condor"), IronCondor)
    assert isinstance(make_strategy("double_diagonal"), DoubleDiagonal)
    assert isinstance(make_strategy("diagonal"), Diagonal)
    assert {"iron_condor", "dacs", "double_diagonal", "diagonal"} <= set(list_strategies())


def test_factory_unknown_raises():
    with pytest.raises(KeyError):
        make_strategy("butterfly")


def test_iron_condor_math():
    c = make_strategy("iron_condor").build(
        underlying="SPY", spot=100.0, dte=45,
        put_long=90.0, put_short=95.0, call_short=105.0, call_long=110.0,
        credit=1.0, sigma=0.20,
    )
    assert len(c.legs) == 4
    assert c.width == pytest.approx(5.0)
    assert c.max_profit == pytest.approx(1.0)
    assert c.max_loss == pytest.approx(4.0)          # width - credit (analytic)
    assert c.breakevens == (94.0, 106.0)
    assert 0.0 < c.pop < 1.0
    assert isinstance(c.score, float)                # expectancy-based; sign is honest
    assert "expected_pnl" in c.meta and "regime_fit" in c.meta


def test_iron_condor_rejects_bad_strikes():
    with pytest.raises(ValueError):
        make_strategy("iron_condor").build(
            underlying="SPY", spot=100.0, dte=45,
            put_long=96.0, put_short=95.0, call_short=105.0, call_long=110.0,
            credit=1.0, sigma=0.20,
        )


def test_regime_fit_favours_condor_in_high_iv():
    from paz_rav.strategies.base import MarketContext
    from paz_rav.strategies.scoring import calendar_fit, condor_fit

    high_iv_range = MarketContext(regime="range / high-vol", iv_rank=70)
    low_iv_range = MarketContext(regime="range / low-vol", iv_rank=20)
    # condor prefers high IV; calendar (diagonals) prefers low IV
    assert condor_fit(high_iv_range) > condor_fit(low_iv_range)
    assert calendar_fit(low_iv_range) > calendar_fit(high_iv_range)
