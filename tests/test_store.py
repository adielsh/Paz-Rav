"""Storage layer — serialization, in-memory stores, and the Redis path (fakeredis).

Async methods are driven with asyncio.run so no pytest-asyncio plugin is needed.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from paz_rav.analytics import iv_rank
from paz_rav.contracts import Feature
from paz_rav.store.memory import (
    InMemoryCandidateRepository,
    InMemoryFeatureStore,
    InMemoryIVHistory,
)
from paz_rav.store.redis_store import RedisFeatureStore, RedisIVHistory
from paz_rav.store.serialize import (
    candidate_from_dict,
    candidate_to_dict,
    feature_from_json,
    feature_to_json,
)
from paz_rav.strategies import make_strategy


def _run(coro):
    return asyncio.run(coro)


def sample_candidate():
    return make_strategy("iron_condor").build(
        underlying="SPY", spot=100.0, dte=45,
        put_long=90.0, put_short=95.0, call_short=105.0, call_long=110.0,
        credit=1.0, sigma=0.20,
    )


def sample_feature():
    return Feature(
        underlying="SPY", spot=100.0, iv_rank=42.0, term_slope=0.05,
        expected_move=5.0, regime="range / high-vol", ts=datetime.now(timezone.utc),
    )


def test_candidate_round_trip():
    c = sample_candidate()
    assert candidate_from_dict(candidate_to_dict(c)) == c


def test_feature_round_trip():
    f = sample_feature()
    f2 = feature_from_json(feature_to_json(f))
    assert (f2.underlying, f2.iv_rank, f2.regime) == (f.underlying, f.iv_rank, f.regime)


def test_memory_feature_store():
    async def go():
        s = InMemoryFeatureStore()
        await s.put(sample_feature())
        return await s.get("SPY")

    assert _run(go()).spot == 100.0


def test_memory_candidate_repo():
    async def go():
        r = InMemoryCandidateRepository()
        await r.save([sample_candidate()])
        return await r.latest("SPY")

    assert len(_run(go())) == 1


def test_iv_history_makes_iv_rank_real():
    async def go():
        h = InMemoryIVHistory()
        now = datetime.now(timezone.utc)
        for v in (0.10, 0.15, 0.20, 0.25, 0.30):
            await h.append("SPY", v, now)
        return await h.window("SPY", 365)

    hist = _run(go())
    assert len(hist) == 5
    assert iv_rank(0.20, hist) == pytest.approx(50.0)   # no longer neutral — computed!


def test_redis_feature_and_iv_history():
    fakeredis = pytest.importorskip("fakeredis")

    async def go():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        fs = RedisFeatureStore(r)
        await fs.put(sample_feature())
        feat = await fs.get("SPY")

        hist = RedisIVHistory(r)
        now = datetime.now(timezone.utc)
        for v in (0.10, 0.20, 0.30):
            await hist.append("SPY", v, now)
        window = await hist.window("SPY", 365)
        return feat, window

    feat, window = _run(go())
    assert feat.iv_rank == 42.0
    assert sorted(window) == [0.10, 0.20, 0.30]
    assert iv_rank(0.20, window) == pytest.approx(50.0)
