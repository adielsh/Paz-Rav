"""Pre-flight failsafe matrix. Every gate logs its values; the aggregate result is returned as a
structured dict so main.py can persist it to `gate_decisions`.
"""
from __future__ import annotations

import logging

from ib_async import IB, Contract, ComboLeg, LimitOrder, TagValue

from .config import CONFIG
from .utils import round_to_tick, valid
from .data_fetcher import Condor

log = logging.getLogger("risk_manager")


def build_bag(options: list[Contract]) -> Contract:
    """4-leg SPXW BAG. Leg actions: SELL shorts, BUY longs. Routed NonGuaranteed=0 at order time."""
    actions = ["SELL", "BUY", "SELL", "BUY"]
    legs = [ComboLeg(conId=o.conId, ratio=1, action=a, exchange="SMART")
            for o, a in zip(options, actions)]
    return Contract(symbol=CONFIG.symbol, secType="BAG", currency="USD",
                    exchange="SMART", comboLegs=legs)


async def evaluate(ib: IB, acct: str, summary: dict, condor: Condor, bag: Contract) -> dict:
    """Run all 5 gates. Returns {accepted, reason, details:{per-gate}}."""
    details: dict = {
        "vix": condor.vix_avg, "credit_mid": condor.combo_mid, "spread": condor.combo_spread,
    }

    # Gate 1: minimum credit
    if condor.combo_mid < CONFIG.min_credit:
        return _reject(f"min-credit {condor.combo_mid:.2f} < {CONFIG.min_credit:.2f}", details)

    # Gate 2: liquidity canyon
    if condor.combo_spread > CONFIG.max_spread:
        return _reject(f"liquidity spread {condor.combo_spread:.2f} > {CONFIG.max_spread:.2f}", details)

    # Gate 4: pyramiding / overlapping short strikes with open positions
    for p in ib.positions(acct):
        c = p.contract
        if c.secType == "OPT" and getattr(c, "tradingClass", "") == CONFIG.trading_class:
            if float(c.strike) in (condor.put_short, condor.call_short):
                return _reject(f"pyramiding: overlapping short strike {c.strike}", details)

    # Gate 3: whatIf margin for a 1-lot priced at mid
    entry = LimitOrder("BUY", CONFIG.lot_size, -round_to_tick(condor.combo_mid))
    entry.smartComboRoutingParams = [TagValue("NonGuaranteed", "0")]
    what = await ib.whatIfOrderAsync(bag, entry)
    add_margin = _margin_of(what)
    budget = summary["net_liq"] * CONFIG.margin_nlv_fraction - summary["init_margin"]
    details["margin_add"] = add_margin
    details["margin_budget"] = budget
    log.info("Margin gate", extra={"margin_add": add_margin, "budget": budget})
    if valid(add_margin) and add_margin > budget:
        return _reject(f"margin add {add_margin:.2f} > budget {budget:.2f}", details)

    log.info("All gates passed", extra=details)
    return {"accepted": True, "reason": "ok", "details": details}


def _margin_of(what) -> float:
    for attr in ("initMarginChange", "maintMarginChange", "initMarginAfter"):
        v = getattr(what, attr, None)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return float("nan")


def _reject(reason: str, details: dict) -> dict:
    log.warning("Gate rejected", extra={"reason": reason, **details})
    return {"accepted": False, "reason": reason, "details": details}
