"""Open-Timing Advisor — deterministic fallback path (no API key, no network).

Mirrors test_close_advisor: the debate must return the full shape offline, ground its
numbers in the candidate, bias sensibly, and cache by setup signature.
"""

import asyncio
from datetime import date

from paz_rav.agents.open_advisor import advise_open, build_open_situation
from paz_rav.strategies import make_strategy

TODAY = date(2026, 1, 15)


def _condor(pop_boost=False):
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=35,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.10 if pop_boost else 0.15, today=TODAY,
        deltas=(-0.05, -0.16, 0.16, 0.05),
    )


def test_situation_carries_computed_numbers_and_deltas():
    c = _condor()
    sit = build_open_situation(c, verdict="take")
    assert sit.short_strikes == [5800.0, 6200.0]
    assert sit.short_deltas == [-0.16, 0.16]      # from the legs, not invented
    assert sit.credit == 20.0 and sit.pop == c.pop
    assert sit.spot == 6000.0                     # finalize() stamped spot into meta
    assert sit.committee_verdict == "take"


def test_advise_open_fallback_shape():
    out = asyncio.run(advise_open(_condor(), verdict="take"))
    assert out["engine"] == "deterministic"       # no API key in tests
    assert out["decision"] in ("open", "wait", "skip")
    assert out["analyst"]["reasons"] and out["critic"]["reasons"]
    assert out["situation"]["underlying"] == "SPX"
    assert "computed_at" in out


def test_advise_open_caches_then_force_recomputes():
    c = _condor()
    a1 = asyncio.run(advise_open(c, verdict="take"))
    a2 = asyncio.run(advise_open(c, verdict="take"))
    assert a1 is a2                                # same setup -> cache hit
    a3 = asyncio.run(advise_open(c, verdict="take", force=True))
    assert a3 is not a1
