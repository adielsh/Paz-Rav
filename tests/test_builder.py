"""Builder — delta-based enumeration, liquidity filtering, and end-to-end build()."""

from datetime import date, datetime, timezone

import pytest

from paz_rav.builder import annotate, build
from paz_rav.contracts import OptionQuote
from paz_rav.quant import black_scholes
from paz_rav.strategies import AnnotatedQuote, BuildConfig, make_strategy

TODAY = date(2026, 1, 15)
EXPIRY = date(2026, 3, 1)  # 45 DTE


def aq(right, strike, delta, mid, *, iv=0.20, oi=100, spread=0.1) -> AnnotatedQuote:
    return AnnotatedQuote(right=right, strike=strike, mid=mid, delta=delta, iv=iv,
                          open_interest=oi, rel_spread=spread)


def sample_chain():
    return [
        aq("put", 85, -0.02, 0.20),
        aq("put", 90, -0.05, 0.50),   # long put wing (95 - 5)
        aq("put", 95, -0.16, 1.20),   # short put (~16 delta)
        aq("put", 98, -0.30, 2.00),
        aq("call", 102, 0.30, 2.00),
        aq("call", 105, 0.16, 1.20),  # short call (~16 delta)
        aq("call", 110, 0.05, 0.50),  # long call wing (105 + 5)
        aq("call", 115, 0.02, 0.20),
    ]


def test_enumerate_picks_target_delta_shorts():
    strat = make_strategy("iron_condor")
    cfg = BuildConfig(short_deltas=(16.0,), wing_widths=(5.0,))
    cands = strat.enumerate(underlying="TST", spot=100.0, dte=45, chain=sample_chain(), config=cfg)

    assert len(cands) == 1
    c = cands[0]
    short_strikes = sorted(leg.strike for leg in c.legs if leg.side == "sell")
    assert short_strikes == [95.0, 105.0]           # the ~16-delta strikes
    assert c.credit == pytest.approx(1.4)           # 1.2 - 0.5 + 1.2 - 0.5
    assert c.width == pytest.approx(5.0)
    assert c.max_loss == pytest.approx(3.6)
    assert 0.0 < c.pop < 1.0
    assert c.score > 0.0


def test_liquidity_filter_rejects_wide_legs():
    strat = make_strategy("iron_condor")
    chain = sample_chain()
    # make the long put illiquid (wide market) — should kill the only candidate
    chain[1] = aq("put", 90, -0.05, 0.50, spread=0.95)
    cfg = BuildConfig(short_deltas=(16.0,), wing_widths=(5.0,), max_rel_spread=0.60)
    assert strat.enumerate(underlying="TST", spot=100.0, dte=45, chain=chain, config=cfg) == []


def test_multiple_deltas_and_widths_produce_more_candidates():
    strat = make_strategy("iron_condor")
    cfg = BuildConfig(short_deltas=(16.0, 30.0), wing_widths=(5.0,))
    cands = strat.enumerate(underlying="TST", spot=100.0, dte=45, chain=sample_chain(), config=cfg)
    assert len(cands) >= 2
    # ranked best-first
    assert cands == sorted(cands, key=lambda c: c.score, reverse=True)


# ---- end-to-end through the builder (annotate computes greeks) ----

def _quote(right, strike, iv=0.20) -> OptionQuote:
    price = black_scholes(100.0, strike, 45 / 365, 0.04, iv, right)
    return OptionQuote(
        underlying="TST", right=right, strike=strike, expiry=EXPIRY,
        bid=max(price - 0.05, 0.01), ask=price + 0.05, implied_vol=iv,
        open_interest=500, ts=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )


def test_annotate_delta_signs():
    quotes = [_quote("call", 100.0), _quote("put", 100.0)]
    ann = annotate(quotes, spot=100.0, config=BuildConfig(), today=TODAY)
    by_right = {a.right: a for a in ann}
    assert by_right["call"].delta > 0
    assert by_right["put"].delta < 0


def test_build_end_to_end_ranks_candidates():
    strikes = [80, 85, 90, 95, 100, 105, 110, 115, 120]
    quotes = [_quote(r, float(k)) for k in strikes for r in ("call", "put")]
    # relax the liquidity gate here (wide OTM spreads are exercised in its own test);
    # this case isolates enumeration + ranking.
    cfg = BuildConfig(short_deltas=(16.0, 30.0), wing_widths=(5.0, 10.0), top_n=5,
                      max_rel_spread=5.0)

    cands = build("TST", spot=100.0, dte=45, quotes=quotes, config=cfg, today=TODAY)

    assert cands, "expected at least one condor"
    assert len(cands) <= 5
    assert cands == sorted(cands, key=lambda c: c.score, reverse=True)
    assert all(c.strategy == "iron_condor" and c.credit > 0 for c in cands)
