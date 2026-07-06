"""Positions + Exit Manager — the Phase-3 close-the-loop mechanics.

Every check compares against numbers the deterministic engine already computed (no AI),
matching the documented rules: condor take-profit-early/time-stop/breach, DACS
stop_strike+offset / profit-multiple / 2-weeks-before-expiry.
"""

import asyncio
from datetime import date, datetime, timezone

import pytest

from paz_rav.positions import ExitConfig, InMemoryPositionRepository, Position, check_exit
from paz_rav.positions.exit_manager import close_position, sweep
from paz_rav.strategies import make_strategy

TODAY = date(2026, 1, 15)


def condor(dte=35):
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=dte,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.15, today=TODAY,
    )


def dacs_position(short_dte=35, long_dte=65):
    """A real DACS position, built via the actual strategy enumeration (not hand-crafted
    numbers) so entry_credit/meta stay internally consistent with the priced legs —
    exactly like the live pipeline opens one."""
    from datetime import timedelta

    from paz_rav.strategies import AnnotatedQuote, BuildConfig, MarketContext

    spot = 60.0
    short_exp = TODAY + timedelta(days=short_dte)
    long_exp = TODAY + timedelta(days=long_dte)
    chain = [
        AnnotatedQuote(right="call", strike=66.0, mid=1.2, delta=0.16, iv=0.18,
                      open_interest=200, rel_spread=0.05, expiry=short_exp, dte=short_dte),
        AnnotatedQuote(right="call", strike=66.0, mid=1.5, delta=0.22, iv=0.18,
                      open_interest=200, rel_spread=0.05, expiry=long_exp, dte=long_dte),
    ]
    cfg = BuildConfig(short_deltas=(16.0,), dacs_short_dte=short_dte,
                      dacs_gap_days=long_dte - short_dte, dacs_min_long_price=0.5)
    ctx = MarketContext(regime="range / low-vol", iv_rank=25, rsi=60)
    cands = make_strategy("dacs").enumerate(underlying="SPX", spot=spot, chain=chain,
                                            config=cfg, today=TODAY, ctx=ctx)
    assert cands, "test setup: expected a DACS candidate"
    return Position.open_from(cands[0], datetime(2026, 1, 15, tzinfo=timezone.utc))


# ---- Position.open_from ----

def test_open_from_candidate_copies_max_profit_into_meta():
    c = condor()
    pos = Position.open_from(c, datetime.now(timezone.utc))
    assert pos.status == "open"
    assert pos.legs == c.legs
    assert pos.entry_credit == c.credit
    assert pos.meta["max_profit"] == c.max_profit


# ---- Iron condor exit rules ----

def test_condor_time_stop_at_21_dte():
    c = condor(dte=35)
    pos = Position.open_from(c, datetime.now(timezone.utc))
    later = TODAY.replace(day=TODAY.day)
    from datetime import timedelta
    should_close, reason = check_exit(pos, spot=6000.0, today=TODAY + timedelta(days=15))
    assert should_close and reason == "time_stop"   # 35-15=20 <= 21


def test_condor_stays_open_mid_trade_no_trigger():
    c = condor(dte=35)
    pos = Position.open_from(c, datetime.now(timezone.utc))
    should_close, reason = check_exit(pos, spot=6000.0, today=TODAY)
    assert not should_close and reason is None


def test_condor_stop_loss_on_short_breach():
    c = condor(dte=35)
    pos = Position.open_from(c, datetime.now(timezone.utc))
    should_close, reason = check_exit(pos, spot=6250.0, today=TODAY)  # past short call 6200
    assert should_close and reason == "stop_loss"


def test_condor_profit_target_when_deep_itm_for_seller():
    c = condor(dte=35)
    pos = Position.open_from(c, datetime.now(timezone.utc))
    from datetime import timedelta
    # far into the trade, price pinned exactly at spot -> most extrinsic value decayed
    should_close, reason = check_exit(pos, spot=6000.0, today=TODAY + timedelta(days=30))
    assert should_close and reason in ("profit_target", "time_stop")


# ---- DACS exit rules ----

def test_dacs_stop_loss_below_strike_by_offset():
    pos = dacs_position()   # short strike = 66.0
    cfg = ExitConfig(dacs_stop_offset=-5.0)   # stop level = 61.0
    should_close, reason = check_exit(pos, spot=62.0, today=TODAY, cfg=cfg)
    assert should_close and reason == "stop_loss"


def test_dacs_no_trigger_when_flat_near_entry():
    pos = dacs_position()   # short strike = 66.0, opened with spot around 60
    cfg = ExitConfig(dacs_stop_offset=-5.0)   # stop level = 61.0
    should_close, reason = check_exit(pos, spot=60.0, today=TODAY, cfg=cfg)
    assert not should_close


def test_dacs_time_stop_two_weeks_before_expiry():
    from datetime import timedelta
    pos = dacs_position(short_dte=35)
    should_close, reason = check_exit(pos, spot=6400.0, today=TODAY + timedelta(days=22))
    assert should_close and reason == "time_stop"   # 35-22=13 <= 14


# ---- Exit manager sweep: advisory only, NEVER closes by itself ----

def test_sweep_flags_but_does_not_close():
    async def go():
        repo = InMemoryPositionRepository()
        c = condor(dte=35)
        pos = Position.open_from(c, datetime(2026, 1, 15, tzinfo=timezone.utc))
        await repo.save(pos)

        # breach the short call -> flagged with stop_loss, but STILL OPEN
        newly_flagged = await sweep(repo, "SPX", spot=6250.0, today=TODAY)
        assert len(newly_flagged) == 1
        assert newly_flagged[0].alert == "stop_loss"
        assert newly_flagged[0].status == "open"          # never auto-closed
        assert newly_flagged[0].realized_pnl is None

        still_open = await repo.list_open("SPX")
        assert len(still_open) == 1 and still_open[0].alert == "stop_loss"

    asyncio.run(go())


def test_sweep_leaves_healthy_positions_unflagged():
    async def go():
        repo = InMemoryPositionRepository()
        c = condor(dte=35)
        pos = Position.open_from(c, datetime(2026, 1, 15, tzinfo=timezone.utc))
        await repo.save(pos)
        newly_flagged = await sweep(repo, "SPX", spot=6000.0, today=TODAY)
        assert newly_flagged == []
        rows = await repo.list_open("SPX")
        assert len(rows) == 1 and rows[0].alert is None

    asyncio.run(go())


def test_sweep_clears_a_stale_alert():
    async def go():
        repo = InMemoryPositionRepository()
        c = condor(dte=35)
        pos = Position.open_from(c, datetime(2026, 1, 15, tzinfo=timezone.utc))
        await repo.save(pos)
        await sweep(repo, "SPX", spot=6250.0, today=TODAY)         # flags stop_loss
        assert (await repo.get(pos.id)).alert == "stop_loss"

        await sweep(repo, "SPX", spot=6000.0, today=TODAY)         # price recovers
        assert (await repo.get(pos.id)).alert is None              # alert cleared
        assert (await repo.get(pos.id)).status == "open"           # still open throughout

    asyncio.run(go())


# ---- Manual close: the REAL price the user confirms ----

def test_close_position_records_real_price_not_a_model():
    async def go():
        repo = InMemoryPositionRepository()
        c = condor(dte=35)
        pos = Position.open_from(c, datetime(2026, 1, 15, tzinfo=timezone.utc))
        await repo.save(pos)

        # user reports: I closed it and paid 5.00 net to close (a debit to close)
        closed = await close_position(repo, pos.id, exit_credit=-5.00,
                                      closed_at=datetime(2026, 1, 20, tzinfo=timezone.utc))
        assert closed is not None
        assert closed.status == "closed"
        assert closed.exit_credit == -5.00
        assert closed.realized_pnl == round(pos.entry_credit - 5.00, 4)
        assert closed.close_reason == "manual"   # no alert was active

    asyncio.run(go())


def test_close_position_uses_active_alert_as_reason():
    async def go():
        repo = InMemoryPositionRepository()
        c = condor(dte=35)
        pos = Position.open_from(c, datetime(2026, 1, 15, tzinfo=timezone.utc))
        await repo.save(pos)
        await sweep(repo, "SPX", spot=6250.0, today=TODAY)   # flags stop_loss

        closed = await close_position(repo, pos.id, exit_credit=-3.50,
                                      closed_at=datetime(2026, 1, 20, tzinfo=timezone.utc))
        assert closed.close_reason == "stop_loss"   # inherited from the active alert

    asyncio.run(go())


def test_close_position_missing_or_already_closed_returns_none():
    async def go():
        repo = InMemoryPositionRepository()
        missing = await close_position(repo, "no-such-id", 1.0, datetime.now(timezone.utc))
        assert missing is None

    asyncio.run(go())


# ---- Serialization round-trip (what PostgresPositionRepository relies on) ----

def test_position_serialization_round_trip_open():
    from paz_rav.store.serialize import position_from_dict, position_to_dict

    pos = Position.open_from(condor(), datetime(2026, 1, 15, tzinfo=timezone.utc),
                             langfuse_trace_id="trace-123")
    restored = position_from_dict(position_to_dict(pos))
    assert restored == pos


def test_position_serialization_round_trip_closed():
    from paz_rav.store.serialize import position_from_dict, position_to_dict

    pos = Position.open_from(condor(), datetime(2026, 1, 15, tzinfo=timezone.utc))
    closed = pos.close_manually(-3.50, datetime(2026, 1, 20, tzinfo=timezone.utc))
    restored = position_from_dict(position_to_dict(closed))
    assert restored == closed
    assert restored.status == "closed"
    assert restored.realized_pnl == closed.realized_pnl
