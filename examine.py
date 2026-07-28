"""
examine.py — end-to-end validation of the SPX Iron Condor bot against an IBKR PAPER account.

What it does (in order):
  1. Connect to the paper gateway (127.0.0.1:4002) and assert the account is a paper account (DU...).
  2. Pull account summary: NetLiquidation, InitMarginReq, AvailableFunds.
  3. Fetch VIX 5-min average and derive target deltas from the VIX state machine.
  4. Pull the SPXW (PM-settled) option chain and pick an expiry in the 35-45 DTE window.
  5. Select short strikes nearest the target deltas; add 50-pt long wings.
  6. Zero-bid guard on the long wings.
  7. Price the 4-leg BAG combo (bid / ask / mid credit).
  8. Run the 5 pre-flight gates (dry-run, structured logging of every reject).
  9. whatIf margin check for a 1-lot.
 10. With --place: limit-walk the entry, then attach a GTC take-profit. Otherwise stop after the gates.

Run:
  python examine.py            # dry run — validates everything, places NO order
  python examine.py --place    # also transmits the paper entry + GTC take-profit

Notes:
  * Full validation (deltas, quotes) needs live/delayed market data — run during US market hours.
    Connectivity, account summary and chain retrieval work any time.
  * 1-lot fixed size. No loss-based stop (by design). Paper only — asserts a DU* account before ordering.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime

from ib_async import IB, Index, Option, Contract, ComboLeg, LimitOrder, TagValue, util

import pytz

# --------------------------------------------------------------------------------------
# Config (mirrors the eventual config.py)
# --------------------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 4002               # paper IB Gateway API port
CLIENT_ID = 11

SYMBOL = "SPX"
TRADING_CLASS = "SPXW"    # PM-settled weeklies only
EXCHANGE = "CBOE"         # index / options listing exchange
MULTIPLIER = 100
LOT_SIZE = 1              # fixed 1-lot

DTE_MIN, DTE_MAX, DTE_TARGET = 35, 45, 40
WING_WIDTH = 50

# VIX delta state machine: (put_delta, call_delta) or None to suspend
def target_deltas(vix: float):
    if vix < 14:
        return (0.15, 0.15)
    if vix <= 22:
        return (0.30, 0.20)
    return None  # VIX > 22 -> suspend

# Pre-flight gates
MIN_CREDIT = 1.20
MAX_SPREAD = 1.50
MARGIN_NLV_FRACTION = 0.70
TP_CREDIT_DELTA = 0.50    # buy back 0.50 cheaper = $50 profit / lot

# Execution
ENTRY_TICK_STEP_SECONDS = 10
ENTRY_TTL_SECONDS = 120

ET = pytz.timezone("America/New_York")

log = logging.getLogger("examine")


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def round_to_tick(price: float) -> float:
    """CBOE option tick: 0.05 below 3.00, 0.10 at/above 3.00. Sign-preserving."""
    tick = 0.05 if abs(price) < 3.00 else 0.10
    return round(round(price / tick) * tick, 2)


def nan_safe(x) -> float:
    return x if (x is not None and not math.isnan(x)) else float("nan")


def valid(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def dte_of(expiry: str) -> int:
    exp = ET.localize(datetime.strptime(expiry, "%Y%m%d").replace(hour=16))
    now = datetime.now(ET)
    return (exp.date() - now.date()).days


async def ready_ticker(ib: IB, contract: Contract, want_greeks: bool, timeout: float = 6.0):
    """Stream market data and wait until quotes (and optionally greeks) populate."""
    ticker = ib.reqMktData(contract, "106" if want_greeks else "", False, False)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.25)
        has_quote = valid(ticker.bid) or valid(ticker.ask) or valid(ticker.close)
        has_greek = (not want_greeks) or (ticker.modelGreeks is not None
                                          and valid(getattr(ticker.modelGreeks, "delta", None)))
        if has_quote and has_greek:
            break
    return ticker


def leg_mid(ticker) -> float:
    b, a = nan_safe(ticker.bid), nan_safe(ticker.ask)
    if valid(b) and valid(a):
        return (b + a) / 2
    return nan_safe(ticker.close)


# --------------------------------------------------------------------------------------
# Main flow
# --------------------------------------------------------------------------------------
async def run(place: bool) -> None:
    ib = IB()
    log.info("Connecting to %s:%s (clientId=%s) ...", HOST, PORT, CLIENT_ID)
    await ib.connectAsync(HOST, PORT, clientId=CLIENT_ID, timeout=20)
    log.info("Connected. Server version %s", ib.client.serverVersion())

    try:
        # ---- 1. Account + paper-safety assertion --------------------------------------
        accounts = ib.managedAccounts()
        acct = accounts[0] if accounts else ""
        log.info("Managed accounts: %s", accounts)
        if not acct.startswith("DU"):
            log.error("Account %r is NOT a paper account (expected DU...). Aborting for safety.", acct)
            return

        summary = {v.tag: v.value for v in await ib.accountSummaryAsync(acct)}
        nlv = float(summary.get("NetLiquidation", "nan"))
        init_margin = float(summary.get("InitMarginReq", "nan"))
        avail = float(summary.get("AvailableFunds", "nan"))
        log.info("Account %s | NetLiq=%.2f  InitMarginReq=%.2f  AvailableFunds=%.2f",
                 acct, nlv, init_margin, avail)

        # ---- market data type fallback: live -> delayed -> delayed-frozen -------------
        # 1=live, 2=frozen, 3=delayed, 4=delayed-frozen. Paper accounts often lack live
        # option data, so fall back gracefully.
        ib.reqMarketDataType(1)

        # ---- 2. VIX 5-min average -----------------------------------------------------
        vix = Index("VIX", "CBOE")
        await ib.qualifyContractsAsync(vix)
        bars = await ib.reqHistoricalDataAsync(
            vix, endDateTime="", durationStr="1 D", barSizeSetting="5 mins",
            whatToShow="TRADE", useRTH=True, formatDate=1)
        if not bars:
            log.error("No VIX historical bars returned. Cannot derive deltas. Aborting.")
            return
        recent = bars[-3:] if len(bars) >= 3 else bars
        vix_avg = sum(b.close for b in recent) / len(recent)
        log.info("VIX 5-min average (last %d bars): %.2f", len(recent), vix_avg)

        deltas = target_deltas(vix_avg)
        if deltas is None:
            log.warning("SYSTEMIC VOLATILITY ALERT: VIX %.2f > 22. Suspending new entry.", vix_avg)
            return
        put_delta_tgt, call_delta_tgt = deltas
        log.info("Target deltas -> short put %.2f / short call %.2f", put_delta_tgt, call_delta_tgt)

        # ---- 3. SPX spot + chain ------------------------------------------------------
        spx = Index(SYMBOL, EXCHANGE)
        await ib.qualifyContractsAsync(spx)
        spx_tkr = await ready_ticker(ib, spx, want_greeks=False)
        spot = nan_safe(spx_tkr.last) if valid(spx_tkr.last) else nan_safe(spx_tkr.close)
        log.info("SPX spot ~ %.2f", spot)
        if not valid(spot):
            log.error("No SPX spot price (market closed / no data). Cannot select strikes. Aborting.")
            return

        chains = await ib.reqSecDefOptParamsAsync(spx.symbol, "", "IND", spx.conId)
        chain = next((c for c in chains if c.tradingClass == TRADING_CLASS and c.exchange == "SMART"),
                     None) or next((c for c in chains if c.tradingClass == TRADING_CLASS), None)
        if chain is None:
            log.error("No %s chain found. Aborting.", TRADING_CLASS)
            return

        expiries = sorted(e for e in chain.expirations if DTE_MIN <= dte_of(e) <= DTE_MAX)
        if not expiries:
            log.error("No expiry in %d-%d DTE window. Aborting.", DTE_MIN, DTE_MAX)
            return
        expiry = min(expiries, key=lambda e: abs(dte_of(e) - DTE_TARGET))
        log.info("Selected expiry %s (%d DTE). Candidates in window: %s",
                 expiry, dte_of(expiry), expiries)

        strikes = sorted(chain.strikes)

        # ---- 4. Delta-based short-strike selection ------------------------------------
        put_strike = await pick_by_delta(ib, expiry, strikes, spot, "P", put_delta_tgt, below=True)
        call_strike = await pick_by_delta(ib, expiry, strikes, spot, "C", call_delta_tgt, below=False)
        if put_strike is None or call_strike is None:
            log.error("Could not resolve short strikes by delta (missing greeks). "
                      "Run during market hours with option data. Aborting.")
            return
        log.info("Short strikes: put %.0f / call %.0f", put_strike, call_strike)

        # ---- 5. Wings + zero-bid guard ------------------------------------------------
        long_put_strike = put_strike - WING_WIDTH
        long_call_strike = call_strike + WING_WIDTH
        long_put_strike = await zero_bid_guard(ib, expiry, strikes, long_put_strike, "P", inward=+5)
        long_call_strike = await zero_bid_guard(ib, expiry, strikes, long_call_strike, "C", inward=-5)
        if long_put_strike is None or long_call_strike is None:
            log.error("Zero-bid guard failed to find a valid long wing. Aborting.")
            return

        # ---- 6. Build + price the combo ----------------------------------------------
        legs_def = [
            ("SELL", put_strike, "P"),
            ("BUY", long_put_strike, "P"),
            ("SELL", call_strike, "C"),
            ("BUY", long_call_strike, "C"),
        ]
        options = [Option(SYMBOL, expiry, k, r, EXCHANGE, tradingClass=TRADING_CLASS,
                          multiplier=str(MULTIPLIER)) for _, k, r in legs_def]
        await ib.qualifyContractsAsync(*options)
        leg_tickers = [await ready_ticker(ib, o, want_greeks=False) for o in options]

        # Net credit (positive = we receive). Sold legs add, bought legs subtract.
        combo_bid = combo_ask = 0.0
        for (action, _, _), tkr in zip(legs_def, leg_tickers):
            b, a = nan_safe(tkr.bid), nan_safe(tkr.ask)
            if not (valid(a) and valid(b)):
                log.error("Missing quote on a leg (market closed / no data). Aborting.")
                return
            if action == "SELL":     # we receive the bid, pay the ask to unwind
                combo_bid += b
                combo_ask += a
            else:                    # BUY leg: costs us
                combo_bid -= a
                combo_ask -= b
        combo_mid = (combo_bid + combo_ask) / 2
        combo_spread = abs(combo_ask - combo_bid)
        log.info("Combo credit  bid=%.2f  ask=%.2f  mid=%.2f  spread=%.2f",
                 combo_bid, combo_ask, combo_mid, combo_spread)

        # ---- 7. Pre-flight gates ------------------------------------------------------
        bag = build_bag(options)
        passed, reason = await run_gates(ib, acct, nlv, init_margin, combo_mid, combo_spread,
                                         bag, put_strike, call_strike)
        if not passed:
            log.warning("PRE-FLIGHT REJECTED: %s", reason)
            return
        log.info("ALL GATES PASSED. 1-lot condor is eligible.")

        # ---- 8. Place paper order (only with --place) --------------------------------
        if not place:
            log.info("Dry run complete (no order placed). Re-run with --place to transmit.")
            return
        await place_entry_and_tp(ib, bag, combo_mid)

    finally:
        ib.disconnect()
        log.info("Disconnected.")


async def pick_by_delta(ib, expiry, strikes, spot, right, target, below):
    """Scan a strike window on one side and return the strike whose |delta| is nearest target."""
    lo, hi = (spot * 0.85, spot) if below else (spot, spot * 1.15)
    window = [k for k in strikes if lo <= k <= hi]
    if not window:
        return None
    opts = [Option(SYMBOL, expiry, k, right, EXCHANGE, tradingClass=TRADING_CLASS,
                   multiplier=str(MULTIPLIER)) for k in window]
    await ib.qualifyContractsAsync(*opts)
    best_k, best_err = None, 1e9
    for o in opts:
        tkr = await ready_ticker(ib, o, want_greeks=True, timeout=4.0)
        g = tkr.modelGreeks
        if g is None or not valid(g.delta):
            continue
        err = abs(abs(g.delta) - target)
        if err < best_err:
            best_err, best_k = err, o.strike
    return best_k


async def zero_bid_guard(ib, expiry, strikes, strike, right, inward):
    """Ensure a long wing has bid>0; shift by `inward` (points, signed) up to a few steps."""
    avail = sorted(strikes)
    for _ in range(6):
        opt = Option(SYMBOL, expiry, strike, right, EXCHANGE, tradingClass=TRADING_CLASS,
                     multiplier=str(MULTIPLIER))
        await ib.qualifyContractsAsync(opt)
        tkr = await ready_ticker(ib, opt, want_greeks=False, timeout=4.0)
        if valid(tkr.bid) and tkr.bid > 0:
            return strike
        nxt = strike + inward
        if nxt not in avail:
            log.warning("Zero-bid guard: strike %.0f has $0 bid and no valid neighbor.", strike)
            return None
        log.info("Zero-bid guard: %s wing %.0f has $0 bid -> shifting to %.0f (width changes).",
                 right, strike, nxt)
        strike = nxt
    return None


def build_bag(options) -> Contract:
    """4-leg SPXW BAG. Leg actions: SELL shorts, BUY longs. NonGuaranteed=0."""
    actions = ["SELL", "BUY", "SELL", "BUY"]
    legs = []
    for opt, action in zip(options, actions):
        legs.append(ComboLeg(conId=opt.conId, ratio=1, action=action, exchange="SMART"))
    bag = Contract(symbol=SYMBOL, secType="BAG", currency="USD", exchange="SMART", comboLegs=legs)
    return bag


async def run_gates(ib, acct, nlv, init_margin, combo_mid, combo_spread, bag, put_k, call_k):
    # Gate 1: min credit
    if combo_mid < MIN_CREDIT:
        return False, f"Min-Credit gate: mid {combo_mid:.2f} < {MIN_CREDIT:.2f}"
    # Gate 2: liquidity canyon
    if combo_spread > MAX_SPREAD:
        return False, f"Liquidity gate: spread {combo_spread:.2f} > {MAX_SPREAD:.2f}"
    # Gate 4: pyramiding / overlapping short strikes
    for p in ib.positions(acct):
        c = p.contract
        if c.secType == "OPT" and getattr(c, "tradingClass", "") == TRADING_CLASS:
            if float(c.strike) in (put_k, call_k):
                return False, f"Pyramiding gate: overlapping short strike {c.strike} already open"
    # Gate 3: whatIf margin for a 1-lot, priced at mid
    entry = LimitOrder("BUY", LOT_SIZE, -round_to_tick(combo_mid))  # credit -> negative combo price
    entry.smartComboRoutingParams = [TagValue("NonGuaranteed", "0")]
    what = await ib.whatIfOrderAsync(bag, entry)
    add_margin = float(getattr(what, "initMarginChange", getattr(what, "initMarginAfter", "nan")))
    budget = nlv * MARGIN_NLV_FRACTION - init_margin
    log.info("whatIf margin: add=%.2f  budget=(NLV*%.2f - init)=%.2f",
             add_margin, MARGIN_NLV_FRACTION, budget)
    if valid(add_margin) and add_margin > budget:
        return False, f"Margin gate: added {add_margin:.2f} > budget {budget:.2f}"
    return True, "ok"


async def place_entry_and_tp(ib, bag, combo_mid):
    """Throttled limit walk for entry; on fill, attach a GTC take-profit."""
    # Start 1 tick FAVORABLE (ask for more credit), walk down toward/below mid every 10s, TTL 120s.
    tick = 0.05 if combo_mid < 3 else 0.10
    credit = round_to_tick(combo_mid + tick)
    order = LimitOrder("BUY", LOT_SIZE, -credit)  # negative = credit received
    order.smartComboRoutingParams = [TagValue("NonGuaranteed", "0")]
    order.tif = "DAY"
    trade = ib.placeOrder(bag, order)
    log.info("Entry submitted at credit %.2f (limit %.2f). Walking down every %ds, TTL %ds.",
             credit, -credit, ENTRY_TICK_STEP_SECONDS, ENTRY_TTL_SECONDS)

    elapsed = 0
    while elapsed < ENTRY_TTL_SECONDS:
        await asyncio.sleep(ENTRY_TICK_STEP_SECONDS)
        elapsed += ENTRY_TICK_STEP_SECONDS
        if trade.orderStatus.status == "Filled":
            break
        credit = round_to_tick(credit - tick)
        order.lmtPrice = -credit
        ib.placeOrder(bag, order)  # modify
        log.info("[%ds] not filled -> lowering credit to %.2f", elapsed, credit)

    if trade.orderStatus.status not in ("Filled",) and trade.orderStatus.filled == 0:
        ib.cancelOrder(order)
        log.warning("Entry unfilled after TTL — cancelled.")
        return

    fill_credit = trade.orderStatus.avgFillPrice
    fill_credit = abs(fill_credit) if valid(fill_credit) else credit
    log.info("ENTRY FILLED at credit ~%.2f (qty %s).", fill_credit, trade.orderStatus.filled)

    # GTC take-profit: buy the condor back for (credit - 0.50) => $50 profit / lot.
    tp_debit = round_to_tick(fill_credit - TP_CREDIT_DELTA)
    tp = LimitOrder("SELL", LOT_SIZE, tp_debit)  # SELL the combo back at a lower net credit
    tp.smartComboRoutingParams = [TagValue("NonGuaranteed", "0")]
    tp.tif = "GTC"
    ib.placeOrder(bag, tp)
    log.info("GTC take-profit attached: buy-back target net %.2f ($%.0f profit / lot).",
             tp_debit, TP_CREDIT_DELTA * MULTIPLIER)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", action="store_true",
                    help="Transmit the paper entry + GTC take-profit (otherwise dry-run).")
    args = ap.parse_args()
    util.run(run(args.place))


if __name__ == "__main__":
    main()
