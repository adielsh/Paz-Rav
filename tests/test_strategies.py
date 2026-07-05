"""Strategy factory + iron condor math. Pure stdlib."""

import pytest

from paz_rav.strategies import IronCondor, list_strategies, make_strategy


def test_factory_returns_registered_strategy():
    strat = make_strategy("iron_condor")
    assert isinstance(strat, IronCondor)
    assert strat.name == "iron_condor"
    assert "iron_condor" in list_strategies()


def test_factory_unknown_raises():
    with pytest.raises(KeyError):
        make_strategy("butterfly")


def test_iron_condor_math():
    strat = make_strategy("iron_condor")
    c = strat.build(
        underlying="SPY",
        spot=100.0,
        dte=45,
        put_long=90.0,
        put_short=95.0,
        call_short=105.0,
        call_long=110.0,
        credit=1.0,
        sigma=0.20,
    )
    assert len(c.legs) == 4
    assert c.width == pytest.approx(5.0)
    assert c.max_profit == pytest.approx(1.0)
    assert c.max_loss == pytest.approx(4.0)          # width - credit
    assert c.breakevens == (94.0, 106.0)             # short_put - credit, short_call + credit
    assert 0.0 < c.pop < 1.0
    assert c.score > 0.0


def test_iron_condor_rejects_bad_strikes():
    strat = make_strategy("iron_condor")
    with pytest.raises(ValueError):
        strat.build(
            underlying="SPY", spot=100.0, dte=45,
            put_long=96.0, put_short=95.0,   # mis-ordered
            call_short=105.0, call_long=110.0,
            credit=1.0, sigma=0.20,
        )
