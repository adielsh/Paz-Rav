"""End-to-end Phase-1 pipeline on the fixture — no network, fully deterministic.

Proves the whole loop: market data -> analytics -> store feature + IV history ->
build -> save candidates -> publish. Also shows IV history accumulating across scans
(which is what makes IV rank real).
"""

import asyncio
from datetime import date
from pathlib import Path

from paz_rav.adapters.market_data import ReplayMarketData
from paz_rav.bus import CH_CANDIDATES, CH_FEATURES, InMemoryBus
from paz_rav.pipeline import Pipeline
from paz_rav.store.memory import (
    InMemoryCandidateRepository,
    InMemoryFeatureStore,
    InMemoryIVHistory,
)
from paz_rav.strategies import BuildConfig

FIXTURE = Path(__file__).parent / "fixtures" / "sample_market.json"
TODAY = date(2026, 1, 15)


def make_pipeline():
    md = ReplayMarketData(FIXTURE)
    return Pipeline(
        md=md,
        feature_store=InMemoryFeatureStore(),
        iv_history=InMemoryIVHistory(),
        candidate_repo=InMemoryCandidateRepository(),
        bus=InMemoryBus(),
        config=BuildConfig(short_deltas=(16.0, 25.0), wing_widths=(5.0, 10.0),
                           max_rel_spread=0.6, top_n=6),
    )


def test_pipeline_run_once_wires_everything():
    p = make_pipeline()

    async def go():
        return await p.run_once("SPY", today=TODAY)

    result = asyncio.run(go())

    assert result is not None
    assert result.feature.underlying == "SPY"
    assert result.feature.spot == 100.0
    assert result.candidates, "expected at least one condor"
    assert result.candidates == sorted(result.candidates, key=lambda c: c.score, reverse=True)

    # feature persisted, candidates persisted, both channels published
    assert asyncio.run(p.feature_store.get("SPY")).spot == 100.0
    assert asyncio.run(p.candidate_repo.latest("SPY"))
    assert p.bus.published[CH_FEATURES]
    assert p.bus.published[CH_CANDIDATES][0]["underlying"] == "SPY"


def test_iv_history_accumulates_across_scans():
    p = make_pipeline()

    async def go():
        await p.run_once("SPY", today=TODAY)
        await p.run_once("SPY", today=TODAY)
        await p.run_once("SPY", today=TODAY)
        return await p.iv_history.window("SPY", 365)

    history = asyncio.run(go())
    assert len(history) == 3           # each scan recorded its ATM IV
    assert all(v > 0 for v in history)
