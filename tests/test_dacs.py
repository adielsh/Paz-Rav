"""DACS 1.0 — call diagonal calendar: strike/delta/expiry rules + stop metadata."""

from datetime import date

from paz_rav.strategies import AnnotatedQuote, BuildConfig, MarketContext, make_strategy

TODAY = date(2026, 1, 15)
SHORT = date(2026, 2, 19)   # ~35 DTE (sell)
LONG = date(2026, 3, 21)    # ~65 DTE (buy, one month beyond)
GOOD = MarketContext(regime="range / low-vol", iv_rank=25, rsi=60, earnings_soon=False)


def aq(right, strike, delta, mid, expiry, dte, *, iv=0.20) -> AnnotatedQuote:
    return AnnotatedQuote(right=right, strike=strike, mid=mid, delta=delta, iv=iv,
                          open_interest=200, rel_spread=0.05, expiry=expiry, dte=dte)


def chain():
    return [
        # front (short) — a ~10% OTM call with delta <= 0.20
        aq("call", 105, 0.30, 2.0, SHORT, 35),
        aq("call", 110, 0.15, 1.2, SHORT, 35),
        # back (long) — same strike, worth > $1
        aq("call", 110, 0.22, 2.0, LONG, 65, iv=0.22),
        aq("call", 115, 0.16, 1.4, LONG, 65, iv=0.22),
    ]


def test_dacs_builds_call_calendar():
    cfg = BuildConfig(dacs_short_dte=35, dacs_gap_days=30, dacs_otm=0.10, dacs_max_delta=0.20)
    cands = make_strategy("dacs").enumerate(
        underlying="TST", spot=100.0, chain=chain(), config=cfg, today=TODAY, ctx=GOOD)

    assert len(cands) == 1
    c = cands[0]
    assert c.strategy == "dacs"
    assert len(c.legs) == 2
    short = next(l for l in c.legs if l.side == "sell")
    long = next(l for l in c.legs if l.side == "buy")
    assert short.strike == 110.0 and short.expiry == SHORT   # ~10% OTM, delta <= 0.2
    assert long.strike == 110.0 and long.expiry == LONG      # same strike, +1 month
    assert c.meta["otm_pct"] == 10.0
    assert c.meta["stop_aggressive"] == 109.0                # short strike - 1
    assert c.meta["stop_conservative"] == 105.0              # short strike - 5
    assert c.meta["fast_ratio"] >= cfg.dacs_min_fast_ratio


def test_dacs_skips_when_earnings_soon():
    cfg = BuildConfig()
    ctx = MarketContext(regime="range / low-vol", iv_rank=25, rsi=60, earnings_soon=True)
    cands = make_strategy("dacs").enumerate(
        underlying="TST", spot=100.0, chain=chain(), config=cfg, today=TODAY, ctx=ctx)
    # earnings hard-zero the regime fit -> score 0 (deprioritized entirely)
    assert all(c.score == 0.0 for c in cands)


def test_dacs_rejects_cheap_long():
    cfg = BuildConfig(dacs_min_long_price=5.0)   # force the $1 long to fail
    cands = make_strategy("dacs").enumerate(
        underlying="TST", spot=100.0, chain=chain(), config=cfg, today=TODAY, ctx=GOOD)
    assert cands == []
