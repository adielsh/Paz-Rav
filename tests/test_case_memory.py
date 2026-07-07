"""Case memory — deterministic vectorization + similarity recall (pure, offline).

The vector is a deterministic function of the computed numbers (never an LLM embedding),
so the whole thing is testable with zero network. Verifies: the vector layout is stable,
similar market states rank as similar, strategy filtering works, and the debate actually
recalls the nearest closed cases and returns them.
"""

import asyncio
from datetime import date, datetime, timezone

from paz_rav.agents.close_advisor import advise, build_situation, situation_vector
from paz_rav.contracts import Feature
from paz_rav.positions import Position
from paz_rav.store.case_memory import (
    VECTOR_DIM,
    InMemoryCaseMemory,
    case_from_position,
    cosine,
    vectorize,
)
from paz_rav.strategies import make_strategy

TODAY = date(2026, 1, 15)


def _condor(dte=35):
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=dte,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.15, today=TODAY,
    )


def _position():
    return Position.open_from(_condor(), datetime(2026, 1, 15, tzinfo=timezone.utc))


def _feature(spot=6000.0):
    return Feature(underlying="SPX", spot=spot, iv_rank=30.0, term_slope=0.0,
                   expected_move=100.0, regime="range / high-vol", rsi=55.0,
                   ts=datetime(2026, 1, 15, tzinfo=timezone.utc))


# ---- Vectorization is deterministic and stable ----

def test_vector_dim_and_determinism():
    kw = dict(strategy="iron_condor", dte=30, pnl_pct_of_max=0.4,
              distance_to_stop_pct=0.03, iv_rank=30.0, rsi=55.0,
              recent_move_pct=0.01, regime="range / high-vol")
    v1 = vectorize(**kw)
    v2 = vectorize(**kw)
    assert v1 == v2                       # deterministic — same inputs, same vector
    assert len(v1) == VECTOR_DIM


def test_similar_states_are_close_distinct_states_are_far():
    base = vectorize(strategy="iron_condor", dte=30, pnl_pct_of_max=0.4,
                     distance_to_stop_pct=0.03, iv_rank=30.0, rsi=55.0,
                     recent_move_pct=0.01, regime="range / high-vol")
    near = vectorize(strategy="iron_condor", dte=28, pnl_pct_of_max=0.42,
                     distance_to_stop_pct=0.03, iv_rank=32.0, rsi=54.0,
                     recent_move_pct=0.01, regime="range / high-vol")
    far = vectorize(strategy="dacs", dte=5, pnl_pct_of_max=-0.5,
                    distance_to_stop_pct=-0.02, iv_rank=90.0, rsi=20.0,
                    recent_move_pct=-0.08, regime="trend / low-vol")
    assert cosine(base, near) > cosine(base, far)


# ---- In-memory recall ----

def test_recall_ranks_by_similarity_and_filters_strategy():
    async def go():
        mem = InMemoryCaseMemory()
        pos = _position()
        # a very similar closed condor (win) and a very different one (loss)
        win = case_from_position(
            pos.close_manually(-2.0, datetime(2026, 1, 20, tzinfo=timezone.utc)),
            vectorize(strategy="iron_condor", dte=34, pnl_pct_of_max=0.45,
                      distance_to_stop_pct=0.033, iv_rank=30.0, rsi=55.0,
                      recent_move_pct=0.0, regime="range / high-vol"))
        loss = case_from_position(
            pos.close_manually(-40.0, datetime(2026, 1, 20, tzinfo=timezone.utc)),
            vectorize(strategy="iron_condor", dte=8, pnl_pct_of_max=-0.9,
                      distance_to_stop_pct=-0.02, iv_rank=95.0, rsi=15.0,
                      recent_move_pct=-0.09, regime="trend / high-vol"))
        await mem.add(win)
        await mem.add(loss)
        assert await mem.count() == 2

        sit = build_situation(_position(), spot=6000.0, today=TODAY, feature=_feature())
        neighbors = await mem.similar(situation_vector(sit), strategy="iron_condor", k=5)
        assert [n.case for n in neighbors][0] is win     # the similar one ranks first
        # strategy filter excludes other strategies entirely
        assert await mem.similar(situation_vector(sit), strategy="dacs", k=5) == []

    asyncio.run(go())


# ---- The debate recalls cases end-to-end (deterministic engine, no network) ----

def test_advise_includes_recalled_cases():
    async def go():
        mem = InMemoryCaseMemory()
        pos = _position()
        mem_case = case_from_position(
            pos.close_manually(-2.0, datetime(2026, 1, 20, tzinfo=timezone.utc)),
            situation_vector(build_situation(pos, spot=6000.0, today=TODAY,
                                             feature=_feature())))
        await mem.add(mem_case)

        out = await advise(_position(), spot=6000.0, today=TODAY, feature=_feature(),
                           memory=mem)
        assert "recalled" in out and len(out["recalled"]) == 1
        assert out["recalled"][0]["summary"] == mem_case.summary
        assert "similarity" in out["recalled"][0]

    asyncio.run(go())


def test_advise_without_memory_has_empty_recalled():
    out = asyncio.run(advise(_position(), spot=6000.0, today=TODAY, feature=_feature()))
    assert out["recalled"] == []
