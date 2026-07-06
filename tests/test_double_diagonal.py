"""Double diagonal — multi-expiry enumeration and grid-priced long legs."""

from datetime import date

from paz_rav.strategies import AnnotatedQuote, BuildConfig, MarketContext, make_strategy

TODAY = date(2026, 1, 15)
FRONT = date(2026, 3, 1)    # 45 DTE  (short legs)
BACK = date(2026, 3, 31)    # 75 DTE  (long legs)
CTX = MarketContext(regime="range / low-vol", iv_rank=20)   # favours long-vega diagonals


def aq(right, strike, delta, mid, expiry, dte, *, iv=0.20) -> AnnotatedQuote:
    return AnnotatedQuote(right=right, strike=strike, mid=mid, delta=delta, iv=iv,
                          open_interest=200, rel_spread=0.05, expiry=expiry, dte=dte)


def two_expiry_chain():
    return [
        # front strangle (short)
        aq("put", 95, -0.16, 1.20, FRONT, 45),
        aq("call", 105, 0.16, 1.20, FRONT, 45),
        aq("put", 98, -0.30, 2.00, FRONT, 45),
        aq("call", 102, 0.30, 2.00, FRONT, 45),
        # back month (long wings, richer IV)
        aq("put", 85, -0.08, 0.60, BACK, 75, iv=0.22),
        aq("put", 90, -0.14, 0.95, BACK, 75, iv=0.22),
        aq("call", 110, 0.14, 0.95, BACK, 75, iv=0.22),
        aq("call", 115, 0.08, 0.60, BACK, 75, iv=0.22),
    ]


def test_double_diagonal_enumerates_across_expiries():
    strat = make_strategy("double_diagonal")
    cfg = BuildConfig(short_deltas=(16.0,), wing_widths=(5.0,), max_rel_spread=0.60)
    cands = strat.enumerate(underlying="TST", spot=100.0, chain=two_expiry_chain(),
                            config=cfg, today=TODAY, ctx=CTX)

    assert cands, "expected a double diagonal"
    c = cands[0]
    assert c.strategy == "double_diagonal"
    assert len(c.legs) == 4

    sells = [leg for leg in c.legs if leg.side == "sell"]
    buys = [leg for leg in c.legs if leg.side == "buy"]
    assert len(sells) == 2 and len(buys) == 2
    assert all(leg.expiry == FRONT for leg in sells)   # shorts are front month
    assert all(leg.expiry == BACK for leg in buys)     # longs are back month
    assert 0.0 < c.pop < 1.0
    assert c.max_loss > 0.0


def test_needs_two_expiries():
    strat = make_strategy("double_diagonal")
    single = [q for q in two_expiry_chain() if q.expiry == FRONT]
    cfg = BuildConfig(short_deltas=(16.0,), wing_widths=(5.0,))
    assert strat.enumerate(underlying="TST", spot=100.0, chain=single,
                           config=cfg, today=TODAY, ctx=CTX) == []
