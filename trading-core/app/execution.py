"""Order execution: throttled limit-walk entry and GTC take-profit attachment.

COMBO PRICE SIGN CONVENTION (matches examine.py, the reference to be paper-validated):
  * The BAG legs are fixed: SELL short put, BUY long put, SELL short call, BUY long call.
  * OPEN the credit condor with action BUY and a NEGATIVE limit price = the credit received
    (e.g. credit 1.20 -> lmtPrice -1.20).
  * CLOSE (take-profit or gamma stop) with action SELL and a POSITIVE limit price = the debit
    paid to buy it back (e.g. buy back for 0.70 -> lmtPrice +0.70).

!! This sign convention is UNVERIFIED against the live API and MUST be confirmed on the paper
   account before any live use. It is the #1 correctness risk in the whole system. !!
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ib_async import IB, Contract, ComboLeg, LimitOrder, TagValue

from .config import CONFIG
from .utils import round_to_tick, tick_for, valid, nan_safe

log = logging.getLogger("execution")


# Leg order stored on the Trade row: [short_put, long_put, short_call, long_call].
_LEG_ACTIONS = ["SELL", "BUY", "SELL", "BUY"]


def rebuild_bag(leg_conids: list[int]) -> Contract:
    """Reconstruct the 4-leg SPXW BAG from the conIds persisted on a Trade row (state recovery)."""
    legs = [ComboLeg(conId=cid, ratio=1, action=a, exchange="SMART")
            for cid, a in zip(leg_conids, _LEG_ACTIONS)]
    return Contract(symbol=CONFIG.symbol, secType="BAG", currency="USD",
                    exchange="SMART", comboLegs=legs)


async def open_gtc_leg_sets(ib: IB) -> list[frozenset]:
    """Return the comboLeg-conId sets of every open GTC combo order (to detect missing take-profits)."""
    out: list[frozenset] = []
    for o in await ib.reqAllOpenOrdersAsync():
        c = getattr(o, "contract", None)
        order = getattr(o, "order", None)
        if c is not None and c.secType == "BAG" and order is not None and order.tif == "GTC":
            out.append(frozenset(leg.conId for leg in c.comboLegs))
    return out


def reattach_gtc(ib: IB, bag: Contract, entry_credit: float) -> float:
    """Place the resting GTC take-profit for a recovered condor (buy back for credit - 0.50)."""
    tp_debit = round_to_tick(entry_credit - CONFIG.tp_credit_delta)
    ib.placeOrder(bag, _combo_order("SELL", tp_debit, tif="GTC"))
    log.info("GTC reattached (state recovery)", extra={"tp_debit": tp_debit})
    return tp_debit


async def close_debit_estimate(ib: IB, leg_conids: list[int]) -> float:
    """Estimate the current net debit to buy the condor back (for the gamma-stop walk start)."""
    from .data_fetcher import ready_ticker  # local import avoids any import-cycle surprises
    debit = 0.0
    for cid, action in zip(leg_conids, _LEG_ACTIONS):
        c = Contract(conId=cid, exchange="SMART")
        await ib.qualifyContractsAsync(c)
        tkr = await ready_ticker(ib, c, want_greeks=False)
        b, a = nan_safe(tkr.bid), nan_safe(tkr.ask)
        mid = (b + a) / 2 if (valid(a) and valid(b)) else nan_safe(tkr.close)
        # Closing reverses each leg: BUY back the shorts (pay), SELL the longs (receive).
        debit += mid if action == "SELL" else -mid
    return round_to_tick(debit)


@dataclass
class EntryResult:
    filled: bool
    fill_credit: float
    quantity: int
    perm_id: int | None
    tp_price: float | None


def _combo_order(action: str, lmt_price: float, tif: str, quantity: int | None = None) -> LimitOrder:
    """Build a combo LimitOrder with an ALREADY-SIGNED net limit price (see module convention)."""
    order = LimitOrder(action, quantity or CONFIG.lot_size, round_to_tick(lmt_price))
    order.smartComboRoutingParams = [TagValue("NonGuaranteed", "0")]
    order.tif = tif
    return order


async def margin_for(ib: IB, bag: Contract, credit: float, quantity: int) -> float:
    """whatIf margin for opening `quantity` lots at `credit` — used to re-check an approved
    proposal, since the entry gate only ever sized the margin for a single lot."""
    from .risk_manager import _margin_of
    probe = _combo_order("BUY", -round_to_tick(credit), tif="DAY", quantity=quantity)
    return _margin_of(await ib.whatIfOrderAsync(bag, probe))


async def place_entry_and_tp(ib: IB, bag: Contract, combo_mid: float,
                             quantity: int | None = None) -> EntryResult:
    """Limit-walk the entry (1 tick favorable, step down every 10s, 120s TTL). On fill, attach GTC TP."""
    qty = quantity or CONFIG.lot_size
    tick = tick_for(combo_mid)
    credit = round_to_tick(combo_mid + tick)          # start 1 tick favorable (ask more credit)
    order = _combo_order("BUY", -credit, tif="DAY", quantity=qty)   # BUY + negative = open for credit
    trade = ib.placeOrder(bag, order)
    log.info("Entry submitted", extra={"credit": credit, "quantity": qty,
                                       "ttl": CONFIG.entry_ttl_seconds})

    elapsed = 0
    while elapsed < CONFIG.entry_ttl_seconds:
        await asyncio.sleep(CONFIG.entry_tick_step_seconds)
        elapsed += CONFIG.entry_tick_step_seconds
        if trade.orderStatus.status == "Filled":
            break
        credit = round_to_tick(credit - tick)          # accept less credit to get filled
        order.lmtPrice = -credit
        ib.placeOrder(bag, order)                      # modify in place
        log.info("Entry walk-down", extra={"elapsed": elapsed, "credit": credit})

    filled_qty = trade.orderStatus.filled or 0
    if trade.orderStatus.status != "Filled" and filled_qty == 0:
        ib.cancelOrder(order)
        log.warning("Entry unfilled after TTL — cancelled")
        return EntryResult(False, 0.0, 0, None, None)

    fill_credit = trade.orderStatus.avgFillPrice
    fill_credit = abs(fill_credit) if valid(fill_credit) else credit
    perm_id = trade.order.permId or None
    log.info("Entry filled", extra={"fill_credit": fill_credit, "qty": filled_qty, "perm_id": perm_id})

    # GTC take-profit: buy the condor back for (credit - 0.50) => $50 profit / lot.
    # Must cover the whole filled size, not one lot, or part of the position is left unprotected.
    tp_debit = round_to_tick(fill_credit - CONFIG.tp_credit_delta)
    tp = _combo_order("SELL", tp_debit, tif="GTC", quantity=int(filled_qty) or qty)
    ib.placeOrder(bag, tp)
    log.info("GTC take-profit attached",
             extra={"tp_debit": tp_debit, "profit_per_lot": CONFIG.tp_credit_delta * CONFIG.multiplier})

    return EntryResult(True, fill_credit, int(filled_qty), perm_id, tp_debit)


async def close_at_market_walk(ib: IB, bag: Contract, start_debit: float) -> bool:
    """Aggressive limit walk to CLOSE an open condor (used by the 25-DTE gamma stop).

    Closing pays a debit. Start at the current mid debit and walk UP (pay more) every 10s until
    filled or TTL.
    """
    tick = tick_for(start_debit)
    debit = round_to_tick(abs(start_debit))
    order = _combo_order("SELL", debit, tif="DAY")     # SELL + positive = close for a debit
    trade = ib.placeOrder(bag, order)
    log.info("Gamma-stop close submitted", extra={"debit": debit})

    elapsed = 0
    while elapsed < CONFIG.entry_ttl_seconds:
        await asyncio.sleep(CONFIG.entry_tick_step_seconds)
        elapsed += CONFIG.entry_tick_step_seconds
        if trade.orderStatus.status == "Filled":
            log.info("Gamma-stop close filled", extra={"debit": debit})
            return True
        debit = round_to_tick(debit + tick)            # pay more to force the exit
        order.lmtPrice = debit
        ib.placeOrder(bag, order)
        log.info("Gamma-stop walk", extra={"elapsed": elapsed, "debit": debit})
    log.warning("Gamma-stop close unfilled after TTL")
    return False
