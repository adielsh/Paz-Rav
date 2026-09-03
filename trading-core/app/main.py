"""trading-core daemon.

Persistent process: connects to the IB gateway, keeps the connection alive, and fires the entry
flow once per trading day at 14:30 ET. Every gate decision and every trade is persisted to Postgres.
On boot it runs state recovery (reattach missing GTC orders — full logic in Phase 6).

Safety: orders are only transmitted when PLACE_ORDERS=1. Default is dry-run (evaluate + persist the
gate decision, place nothing). The paper-account guard in data_fetcher.connect() still applies.

Manual approval: with REQUIRE_APPROVAL=1 (the default) a condor that passes every gate is NOT
transmitted. It is written to `trade_proposals` as 'pending' and surfaced in the UI, where a person
approves or rejects it. Approved proposals are re-priced and re-validated here before placing.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date

from ib_async import IB

from .config import CONFIG
from .logging_config import setup_logging
from . import db
from .data_fetcher import connect, account_summary, vix_average, build_condor, PaperAccountError
from .risk_manager import evaluate, build_bag
from .execution import (place_entry_and_tp, rebuild_bag, open_gtc_leg_sets, reattach_gtc,
                        close_debit_estimate, close_at_market_walk, margin_for)
from .utils import now_et, is_entry_time_open, dte_of

log = logging.getLogger("main")

PLACE_ORDERS = os.getenv("PLACE_ORDERS", "0") == "1"
POLL_SECONDS = 30
# Entry retries inside one daily window before the day is written off. The window is ~29
# minutes at a 30s poll, so this bounds it without burning the whole window on a hard failure.
MAX_ENTRY_ATTEMPTS = int(os.getenv("MAX_ENTRY_ATTEMPTS", "20"))


def _open_trades(session_factory) -> list:
    """Live open condors only — demo/seed rows are never real positions (see db.Trade.is_demo)."""
    from sqlalchemy import select
    with session_factory() as s:
        return s.execute(select(db.Trade).where(
            db.Trade.status == "open", db.Trade.is_demo.is_(False))).scalars().all()


async def state_recovery(ib: IB, acct: str, session_factory) -> None:
    """Reconcile DB open condors against IBKR open orders; reattach any missing GTC take-profit.

    The DB is the definition of record (leg conIds + entry credit). We only reattach when no GTC
    combo order with the same leg set is already resting at IBKR — so this is idempotent.
    """
    trades = _open_trades(session_factory)
    if not trades:
        log.info("State recovery: no open condors")
        return
    if PLACE_ORDERS:
        existing = await open_gtc_leg_sets(ib)
    else:
        existing = []
    reattached = 0
    for t in trades:
        if not t.leg_conids:
            log.warning("State recovery: trade missing leg_conids", extra={"trade_id": t.id})
            continue
        leg_set = frozenset(t.leg_conids)
        if leg_set in existing:
            continue
        log.info("State recovery: GTC missing for open condor", extra={"trade_id": t.id})
        if PLACE_ORDERS:
            reattach_gtc(ib, rebuild_bag(t.leg_conids), t.entry_credit)
            reattached += 1
    log.info("State recovery complete",
             extra={"open": len(trades), "reattached": reattached, "place_orders": PLACE_ORDERS})


async def gamma_scan(ib: IB, acct: str, session_factory) -> None:
    """25-DTE gamma stop: force-close any open condor at/under the DTE threshold via a limit walk."""
    for t in _open_trades(session_factory):
        if dte_of(t.expiry) > CONFIG.gamma_stop_dte:
            continue
        log.info("Gamma stop triggered", extra={"trade_id": t.id, "expiry": t.expiry,
                                                 "dte": dte_of(t.expiry)})
        if not PLACE_ORDERS:
            log.info("Gamma stop: PLACE_ORDERS=0 (dry-run) — not closing", extra={"trade_id": t.id})
            continue
        bag = rebuild_bag(t.leg_conids)
        start_debit = await close_debit_estimate(ib, t.leg_conids)
        closed = await close_at_market_walk(ib, bag, start_debit)
        if closed:
            _persist_close(session_factory, t.id, start_debit, "gamma_exit", "stopped")


def _already_traded_today(session_factory) -> bool:
    """Pyramiding gate (part 1): at most ONE new combo per calendar day (ET)."""
    from sqlalchemy import select
    today = now_et().date()
    with session_factory() as s:
        rows = s.execute(select(db.Trade)).scalars().all()
        return any(t.created_at and t.created_at.astimezone(now_et().tzinfo).date() == today
                   for t in rows)


async def run_entry_flow(ib: IB, acct: str, session_factory) -> None:
    """One full entry attempt: VIX -> condor -> gates -> persist -> (optional) place order."""
    if not db.trading_enabled():
        log.warning("Kill switch active (control.trading_enabled=false) — skipping entry")
        return
    if _already_traded_today(session_factory):
        log.info("Pyramiding gate: already traded today — skipping")
        return
    if CONFIG.require_approval and _pending_proposal_today(session_factory):
        log.info("A proposal already exists for today — skipping")
        return

    summary = await account_summary(ib, acct)
    vix = await vix_average(ib)
    log.info("VIX average", extra={"vix": vix, **summary})

    condor = await build_condor(ib, vix)  # None => VIX>22 suspend
    if condor is None:
        _persist_gate(session_factory, vix, False, "VIX>22 systemic volatility suspend", {"vix": vix})
        return

    bag = build_bag(condor.options)
    decision = await evaluate(ib, acct, summary, condor, bag)
    _persist_gate(session_factory, vix, decision["accepted"], decision["reason"], decision["details"])
    if not decision["accepted"]:
        return

    # Human in the loop: park the condor for approval rather than transmitting it now.
    #
    # This runs in dry-run too, and must: process_proposals() re-checks PLACE_ORDERS before
    # it transmits anything, so writing a proposal cannot move money. Checking PLACE_ORDERS
    # first — as this did — made the approval queue unreachable in the shipped defaults
    # (PLACE_ORDERS=0, REQUIRE_APPROVAL=1), so trade_proposals stayed empty forever and the
    # console's approvals page could never show anything.
    if CONFIG.require_approval:
        pid = _persist_proposal(session_factory, condor, decision["details"])
        log.info("Entry parked for manual approval",
                 extra={"proposal_id": pid, "credit": condor.combo_mid,
                        "place_orders": PLACE_ORDERS})
        return

    if not PLACE_ORDERS:
        log.info("Gates passed but PLACE_ORDERS=0 (dry-run) — no order transmitted")
        return

    result = await place_entry_and_tp(ib, bag, condor.combo_mid)
    if result.filled:
        _persist_trade(session_factory, condor, result)


def _persist_proposal(session_factory, condor, gate_details: dict) -> int:
    """Park a gate-approved condor as a pending proposal and return its id."""
    from datetime import timedelta
    with session_factory() as s:
        p = db.TradeProposal(
            user_id=db.owner_user_id(),
            status="pending", expiry=condor.expiry, dte=condor.dte, vix_avg=condor.vix_avg,
            put_short_strike=condor.put_short, put_long_strike=condor.put_long,
            call_short_strike=condor.call_short, call_long_strike=condor.call_long,
            target_put_delta=condor.put_delta_tgt, target_call_delta=condor.call_delta_tgt,
            quantity=CONFIG.lot_size,
            combo_bid=_f(condor.combo_bid), combo_ask=_f(condor.combo_ask),
            combo_mid=_f(condor.combo_mid), combo_spread=_f(condor.combo_spread),
            leg_conids=[o.conId for o in condor.options], gate_details=gate_details,
            expires_at=_utcnow() + timedelta(minutes=CONFIG.proposal_ttl_minutes),
        )
        s.add(p)
        s.commit()
        return p.id


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _f(v) -> float | None:
    """NaN is not JSON- or Postgres-friendly; store it as NULL."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _pending_proposal_today(session_factory) -> bool:
    """A proposal already raised today counts as 'traded' for the pyramiding gate, so a
    daemon restart cannot re-propose the same day."""
    from sqlalchemy import select
    today = now_et().date()
    with session_factory() as s:
        rows = s.execute(select(db.TradeProposal)).scalars().all()
        return any(p.created_at and p.created_at.astimezone(now_et().tzinfo).date() == today
                   and p.status in ("pending", "approved", "placed") for p in rows)


async def process_proposals(ib: IB, acct: str, session_factory) -> None:
    """Expire stale pending proposals, then place the ones a human approved.

    Approval is intent, not a price lock: the quote that produced the proposal is minutes or
    hours old by now, so every approved proposal is re-priced and re-checked against the
    kill switch and the minimum-credit gate before anything is transmitted.
    """
    from sqlalchemy import select
    now = _utcnow()

    with session_factory() as s:
        for p in s.execute(select(db.TradeProposal)
                           .where(db.TradeProposal.status == "pending")).scalars().all():
            if p.expires_at and p.expires_at <= now:
                p.status = "expired"
                log.info("Proposal expired", extra={"proposal_id": p.id})
        s.commit()

    with session_factory() as s:
        approved = s.execute(select(db.TradeProposal)
                             .where(db.TradeProposal.status == "approved")).scalars().all()
        pending_ids = [p.id for p in approved]
    if not pending_ids:
        return

    for pid in pending_ids:
        with session_factory() as s:
            p = s.get(db.TradeProposal, pid)
            if p is None or p.status != "approved":
                continue
            spec = {c.name: getattr(p, c.name) for c in p.__table__.columns}

        fail = None
        if not PLACE_ORDERS:
            fail = "PLACE_ORDERS=0 (dry-run) — order not transmitted"
        elif not db.trading_enabled():
            fail = "kill switch active"
        elif not spec.get("leg_conids"):
            fail = "proposal has no leg conIds"

        qty = max(1, int(spec.get("quantity") or CONFIG.lot_size))
        if fail is None:
            try:
                bag = rebuild_bag(spec["leg_conids"])
                # Re-price: same net as the close estimate, opposite intent (credit to open).
                credit = await close_debit_estimate(ib, spec["leg_conids"])
                margin = await margin_for(ib, bag, credit, qty) if credit == credit else float("nan")
                summary = await account_summary(ib, acct)
                budget = summary["net_liq"] * CONFIG.margin_nlv_fraction - summary["init_margin"]
                if not credit or credit != credit:
                    fail = "could not re-price the combo (no quotes)"
                elif credit < CONFIG.min_credit:
                    fail = f"re-priced credit {credit:.2f} < min {CONFIG.min_credit:.2f}"
                # The entry gate sized margin for ONE lot. The approver may have asked for more,
                # so the real size has to clear the budget before anything is transmitted.
                elif margin == margin and margin > budget:
                    fail = f"margin {margin:.0f} for {qty} lot(s) > budget {budget:.0f}"
                else:
                    log.info("Placing approved proposal",
                             extra={"proposal_id": pid, "snapshot_credit": spec["combo_mid"],
                                    "repriced_credit": credit, "quantity": qty, "margin": margin})
                    result = await place_entry_and_tp(ib, bag, credit, quantity=qty)
                    if result.filled:
                        tid = _persist_trade_from_proposal(session_factory, spec, result)
                        _finish_proposal(session_factory, pid, "placed",
                                         trade_id=tid, credit=result.fill_credit)
                        continue
                    fail = "entry unfilled after TTL"
            except Exception as e:                       # noqa: BLE001 — surface it in the UI
                log.exception("Approved proposal failed", extra={"proposal_id": pid})
                fail = f"{type(e).__name__}: {e}"[:250]

        log.warning("Proposal not placed", extra={"proposal_id": pid, "error": fail})
        _finish_proposal(session_factory, pid, "failed", error=fail)


def _finish_proposal(session_factory, pid: int, status: str, trade_id: int | None = None,
                     error: str | None = None, credit: float | None = None) -> None:
    with session_factory() as s:
        p = s.get(db.TradeProposal, pid)
        if p is None:
            return
        p.status = status
        p.trade_id = trade_id
        p.error = error
        p.placed_credit = credit
        s.commit()


def _persist_trade_from_proposal(session_factory, spec: dict, result) -> int:
    with session_factory() as s:
        t = db.Trade(
            user_id=spec.get("user_id") or db.owner_user_id(),
            expiry=spec["expiry"], dte=spec["dte"], vix_avg=spec["vix_avg"],
            put_short_strike=spec["put_short_strike"], put_long_strike=spec["put_long_strike"],
            call_short_strike=spec["call_short_strike"], call_long_strike=spec["call_long_strike"],
            target_put_delta=spec["target_put_delta"], target_call_delta=spec["target_call_delta"],
            entry_credit=result.fill_credit,
            quantity=result.quantity or spec.get("quantity") or CONFIG.lot_size, status="open",
            ib_perm_id=result.perm_id, leg_conids=spec["leg_conids"],
        )
        s.add(t)
        s.flush()
        s.add(db.Fill(trade_id=t.id, kind="entry", price=result.fill_credit,
                      quantity=result.quantity))
        s.commit()
        log.info("Trade persisted from proposal", extra={"trade_id": t.id,
                                                         "credit": result.fill_credit})
        return t.id


def _persist_gate(session_factory, vix, accepted, reason, details) -> None:
    with session_factory() as s:
        s.add(db.GateDecision(user_id=db.owner_user_id(), vix=vix, accepted=accepted,
                              reason=reason, details=details))
        s.commit()


def _persist_close(session_factory, trade_id: int, debit: float, kind: str, status: str) -> None:
    """Record a close: fill + realized P&L (credit received - debit paid, x multiplier x qty) + status."""
    from datetime import datetime, timezone
    with session_factory() as s:
        t = s.get(db.Trade, trade_id)
        if t is None:
            return
        realized = (t.entry_credit - debit) * CONFIG.multiplier * t.quantity
        s.add(db.Fill(trade_id=trade_id, kind=kind, price=debit, quantity=t.quantity))
        s.add(db.Pnl(trade_id=trade_id, realized=realized))
        t.status = status
        t.closed_at = datetime.now(timezone.utc)
        s.commit()
        log.info("Trade closed", extra={"trade_id": trade_id, "status": status, "realized": realized})


def _persist_trade(session_factory, condor, result) -> None:
    with session_factory() as s:
        t = db.Trade(
            user_id=db.owner_user_id(),
            expiry=condor.expiry, dte=condor.dte, vix_avg=condor.vix_avg,
            put_short_strike=condor.put_short, put_long_strike=condor.put_long,
            call_short_strike=condor.call_short, call_long_strike=condor.call_long,
            target_put_delta=condor.put_delta_tgt, target_call_delta=condor.call_delta_tgt,
            entry_credit=result.fill_credit, quantity=result.quantity, status="open",
            ib_perm_id=result.perm_id, leg_conids=[o.conId for o in condor.options],
        )
        s.add(t)
        s.flush()
        s.add(db.Fill(trade_id=t.id, kind="entry", price=result.fill_credit, quantity=result.quantity))
        s.commit()
        log.info("Trade persisted", extra={"trade_id": t.id, "credit": result.fill_credit})


async def daemon() -> None:
    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    session_factory = db.init_db()
    log.info("trading-core starting", extra={"place_orders": PLACE_ORDERS,
                                             "require_approval": CONFIG.require_approval,
                                             "ib": f"{CONFIG.ib_host}:{CONFIG.ib_port}"})
    ib = IB()
    acct = await _connect_with_retry(ib)
    await state_recovery(ib, acct, session_factory)

    ran_on: date | None = None
    announced: date | None = None      # so "window reached" is logged once, not every poll
    attempts = 0                        # entry attempts made inside today's window
    while True:
        try:
            if not ib.isConnected():
                acct = await _connect_with_retry(ib)
                await state_recovery(ib, acct, session_factory)

            # Approvals are acted on every tick, not just in the entry window — the person
            # approving may click long after 14:30.
            await process_proposals(ib, acct, session_factory)

            now = now_et()
            due = (now.hour, now.minute) >= (CONFIG.entry_hour, CONFIG.entry_minute)
            in_window = due and now.hour == CONFIG.entry_hour  # 14:30-14:59 guard band
            if in_window and ran_on != now.date() and is_entry_time_open(now.date()):
                if announced != now.date():
                    log.info("Daily window reached", extra={"date": str(now.date())})
                    announced, attempts = now.date(), 0
                await gamma_scan(ib, acct, session_factory)     # close 25-DTE positions first
                try:
                    await run_entry_flow(ib, acct, session_factory)
                    ran_on = now.date()
                except Exception as e:
                    # Retry within the window, but make the failure visible: without this a
                    # broken entry only ever showed up in the daemon log, never in the UI.
                    attempts += 1
                    log.exception("Entry flow failed", extra={"attempt": attempts})
                    if attempts == 1 or attempts % 10 == 0:
                        _persist_gate(session_factory, None, False,
                                      f"entry flow error: {type(e).__name__}: {e}"[:250],
                                      {"attempt": attempts})
                    if attempts >= MAX_ENTRY_ATTEMPTS:
                        log.error("Giving up on today's entry",
                                  extra={"attempts": attempts, "date": str(now.date())})
                        ran_on = now.date()
        except PaperAccountError:
            raise
        except Exception:
            log.exception("Daemon loop error")
        await asyncio.sleep(POLL_SECONDS)


async def _connect_with_retry(ib: IB, attempts: int = 30) -> str:
    for i in range(attempts):
        try:
            return await connect(ib)
        except PaperAccountError:
            raise
        except Exception as e:
            log.warning("IB connect failed, retrying", extra={"attempt": i + 1, "error": str(e)})
            await asyncio.sleep(5)
    raise RuntimeError("Could not connect to IB gateway after retries.")


def run() -> None:
    from ib_async import util
    util.run(daemon())


if __name__ == "__main__":
    run()
