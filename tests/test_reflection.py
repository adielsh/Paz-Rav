"""Strategic reflection agent — deterministic aggregation + honest sample gating (offline).

With ANTHROPIC_API_KEY empty (conftest guarantees it), reflect() runs the rule-based path,
so every number is verifiable and no network is touched. Verifies: aggregates are computed
correctly, the minimum-sample gate refuses to pattern-match on noise, recommendations are
grounded, and the reflection persists + reloads for continuity.
"""

import asyncio
from datetime import datetime, timezone

from paz_rav.agents.reflection import (
    MIN_SAMPLE,
    aggregate_stats,
    reflect,
    reflection_from_dict,
    reflection_to_dict,
)
from paz_rav.store.reflection_repo import InMemoryReflectionRepository


class _Pos:
    """Minimal closed-position stand-in (reflection only reads these fields)."""

    def __init__(self, strategy, underlying, realized_pnl, close_reason):
        self.strategy = strategy
        self.underlying = underlying
        self.realized_pnl = realized_pnl
        self.close_reason = close_reason
        self.status = "closed"


def _history(n_win_ic=8, n_loss_ic=2, n_dacs_loss=4):
    rows = []
    rows += [_Pos("iron_condor", "SPX", 12.0, "profit_target") for _ in range(n_win_ic)]
    rows += [_Pos("iron_condor", "SPX", -40.0, "stop_loss") for _ in range(n_loss_ic)]
    rows += [_Pos("dacs", "QQQ", -5.0, "stop_loss") for _ in range(n_dacs_loss)]
    return rows


# ---- Deterministic aggregation ----

def test_aggregate_stats_computes_buckets():
    stats = aggregate_stats(_history())
    assert stats["sample_size"] == 14
    ic = stats["by_strategy"]["iron_condor"]
    assert ic["count"] == 10
    assert ic["win_rate"] == 0.8                      # 8 of 10 winners
    dacs = stats["by_strategy"]["dacs"]
    assert dacs["win_rate"] == 0.0 and dacs["count"] == 4
    assert stats["by_close_reason"]["stop_loss"]["count"] == 6


def test_aggregate_stats_empty():
    stats = aggregate_stats([])
    assert stats["sample_size"] == 0 and stats["by_strategy"] == {}


# ---- Honest minimum-sample gate ----

def test_reflect_refuses_below_min_sample():
    closed = _history(n_win_ic=2, n_loss_ic=0, n_dacs_loss=0)   # 2 < MIN_SAMPLE
    r = asyncio.run(reflect(closed))
    assert r.enough_data is False
    assert r.sample_size == 2 < MIN_SAMPLE
    assert r.recommendations == []


# ---- Rule-based reflection is grounded in the stats ----

def test_reflect_fallback_flags_losing_strategy():
    r = asyncio.run(reflect(_history()))
    assert r.enough_data is True
    assert r.engine == "deterministic"                # no API key in tests
    assert r.recommendations                          # at least one suggestion
    joined = " ".join(r.recommendations)
    assert "dacs" in joined                            # the losing bucket is called out


# ---- Persistence + continuity round-trip ----

def test_reflection_repo_recent_newest_first_and_round_trip():
    async def go():
        repo = InMemoryReflectionRepository()
        older = await reflect(_history())
        await repo.save(older)
        # a second, later reflection
        newer = await reflect(_history(n_win_ic=9))
        object.__setattr__(newer, "created_at", datetime.now(timezone.utc))
        await repo.save(newer)

        recent = await repo.recent(5)
        assert len(recent) == 2
        assert recent[0].created_at >= recent[1].created_at   # newest first

        restored = reflection_from_dict(reflection_to_dict(older))
        assert restored.summary == older.summary
        assert restored.stats == older.stats

    asyncio.run(go())
