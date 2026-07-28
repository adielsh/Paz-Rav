"""IB-facing read layer: connection, account, VIX, chain, greeks/quotes, halt + zero-bid guards.

Refactored from the validated examine.py reference logic. No orders are placed here.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ib_async import IB, Index, Option, Contract

from .config import CONFIG
from .utils import valid, nan_safe, dte_of

log = logging.getLogger("data_fetcher")


class PaperAccountError(RuntimeError):
    """Raised when the connected account is not a paper account and the guard is active."""


@dataclass
class Condor:
    expiry: str
    dte: int
    vix_avg: float
    put_delta_tgt: float
    call_delta_tgt: float
    put_short: float
    put_long: float
    call_short: float
    call_long: float
    options: list          # [short_put, long_put, short_call, long_call] qualified Options
    combo_bid: float = float("nan")
    combo_ask: float = float("nan")
    combo_mid: float = float("nan")
    combo_spread: float = float("nan")


def _opt(expiry: str, strike: float, right: str) -> Option:
    return Option(CONFIG.symbol, expiry, strike, right, CONFIG.exchange,
                  tradingClass=CONFIG.trading_class, multiplier=str(CONFIG.multiplier))


async def connect(ib: IB) -> str:
    """Connect and return the managed account id, asserting it's a paper account."""
    await ib.connectAsync(CONFIG.ib_host, CONFIG.ib_port, clientId=CONFIG.ib_client_id, timeout=20)
    accounts = ib.managedAccounts()
    acct = accounts[0] if accounts else ""
    if CONFIG.paper_account_prefix and not acct.startswith(CONFIG.paper_account_prefix):
        raise PaperAccountError(
            f"Account {acct!r} is not a paper account (expected {CONFIG.paper_account_prefix}*).")
    # Without this every quote comes back empty on an account with no live data subscription:
    # IBKR answers "not subscribed" rather than falling back to delayed on its own.
    ib.reqMarketDataType(CONFIG.market_data_type)
    log.info("Connected", extra={"account": acct, "server_version": ib.client.serverVersion(),
                                 "market_data_type": CONFIG.market_data_type})
    if CONFIG.market_data_type != 1:
        log.warning("Delayed market data in use — quotes lag ~15 minutes; entry prices "
                    "derived from them are NOT execution-grade",
                    extra={"market_data_type": CONFIG.market_data_type})
    return acct


async def account_summary(ib: IB, acct: str) -> dict:
    rows = {v.tag: v.value for v in await ib.accountSummaryAsync(acct)}
    return {
        "net_liq": float(rows.get("NetLiquidation", "nan")),
        "init_margin": float(rows.get("InitMarginReq", "nan")),
        "avail_funds": float(rows.get("AvailableFunds", "nan")),
    }


async def ready_ticker(ib: IB, contract: Contract, want_greeks: bool, timeout: float = 6.0,
                       keep: bool = False):
    """Stream market data until quotes (and optionally model greeks) populate, or timeout.

    The subscription is released before returning. IBKR caps concurrent market-data lines
    (~100); a delta scan touches far more strikes than that, so holding every line open ran
    the account out of tickers ("Max number of tickers has been reached") and every request
    after that silently returned nothing. Pass keep=True to hold a line open deliberately.
    """
    ticker = ib.reqMktData(contract, "106" if want_greeks else "", False, False)
    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.25)
            has_quote = valid(ticker.bid) or valid(ticker.ask) or valid(ticker.close)
            has_greek = (not want_greeks) or (ticker.modelGreeks is not None
                                              and valid(getattr(ticker.modelGreeks, "delta", None)))
            if has_quote and has_greek:
                break
        return ticker
    finally:
        if not keep:
            try:
                ib.cancelMktData(contract)
            except Exception:                     # already gone / never started
                pass


async def any_halted(ib: IB, contracts: list[Contract]) -> bool:
    """Circuit breaker: True if the index or any option leg reports a halted tick."""
    for c in contracts:
        tkr = await ready_ticker(ib, c, want_greeks=False, timeout=4.0)
        if valid(tkr.halted) and tkr.halted > 0:
            log.warning("Halt detected", extra={"conId": c.conId, "symbol": c.symbol})
            return True
    return False


async def vix_average(ib: IB, attempts: int = 3) -> float:
    """5-min VIX average (mean of the last few 5-min bars) to dodge single-tick zero glitches.

    Retried: this is the first call of the entry flow and the daily window is only ~29 minutes,
    so one transient historical-data hiccup used to cost the whole trading day.
    """
    vix = Index("VIX", "CBOE")
    await ib.qualifyContractsAsync(vix)
    for i in range(attempts):
        # whatToShow must be "TRADES" (plural). "TRADE" is not a valid value and IBKR answers
        # it with silence, so the request just times out — that blocked every entry attempt.
        bars = await ib.reqHistoricalDataAsync(
            vix, endDateTime="", durationStr="1 D", barSizeSetting="5 mins",
            whatToShow="TRADES", useRTH=True, formatDate=1)
        if bars:
            recent = bars[-3:] if len(bars) >= 3 else bars
            return sum(b.close for b in recent) / len(recent)
        log.warning("No VIX bars returned — retrying",
                    extra={"attempt": i + 1, "attempts": attempts})
        await asyncio.sleep(2 * (i + 1))
    raise RuntimeError(f"No VIX historical bars returned after {attempts} attempts.")


async def spx_spot(ib: IB) -> tuple[Index, float]:
    spx = Index(CONFIG.symbol, CONFIG.exchange)
    await ib.qualifyContractsAsync(spx)
    tkr = await ready_ticker(ib, spx, want_greeks=False)
    spot = nan_safe(tkr.last) if valid(tkr.last) else nan_safe(tkr.close)
    return spx, spot


async def select_chain_and_expiry(ib: IB, spx: Index):
    """Return (chain, expiry, sorted_strikes) for the SPXW expiry nearest DTE_TARGET in-window."""
    chains = await ib.reqSecDefOptParamsAsync(spx.symbol, "", "IND", spx.conId)
    chain = (next((c for c in chains if c.tradingClass == CONFIG.trading_class and c.exchange == "SMART"),
                  None)
             or next((c for c in chains if c.tradingClass == CONFIG.trading_class), None))
    if chain is None:
        raise RuntimeError(f"No {CONFIG.trading_class} chain found.")
    in_window = sorted(e for e in chain.expirations if CONFIG.dte_min <= dte_of(e) <= CONFIG.dte_max)
    if not in_window:
        raise RuntimeError(f"No expiry in {CONFIG.dte_min}-{CONFIG.dte_max} DTE window.")
    expiry = min(in_window, key=lambda e: abs(dte_of(e) - CONFIG.dte_target))
    return chain, expiry, sorted(chain.strikes)


async def pick_by_delta(ib: IB, expiry: str, strikes: list[float], spot: float,
                        right: str, target: float, below: bool) -> float | None:
    """Scan one side of the chain; return the strike whose |delta| is nearest target."""
    lo, hi = (spot * 0.85, spot) if below else (spot, spot * 1.15)
    window = [k for k in strikes if lo <= k <= hi]
    if not window:
        return None
    opts = [_opt(expiry, k, right) for k in window]
    await ib.qualifyContractsAsync(*opts)
    # The chain advertises strikes across ALL expiries, so many don't exist for this one and
    # come back unqualified. Requesting market data on those raises — drop them first.
    opts = [o for o in opts if o.conId]
    if not opts:
        log.warning("No strikes qualified on this side", extra={"expiry": expiry, "right": right})
        return None
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


async def zero_bid_guard(ib: IB, expiry: str, strikes: list[float], strike: float,
                         right: str, inward: int) -> float | None:
    """Ensure a long wing has bid>0; shift by `inward` points up to a few steps. Logs width change."""
    avail = set(strikes)
    for _ in range(6):
        opt = _opt(expiry, strike, right)
        await ib.qualifyContractsAsync(opt)
        if not opt.conId:                     # strike not listed for this expiry — step inward
            log.info("Zero-bid guard: strike not listed", extra={"strike": strike, "right": right})
        else:
            tkr = await ready_ticker(ib, opt, want_greeks=False, timeout=4.0)
            if valid(tkr.bid) and tkr.bid > 0:
                return strike
        nxt = strike + inward
        if nxt not in avail:
            log.warning("Zero-bid guard: no valid neighbor", extra={"strike": strike, "right": right})
            return None
        log.info("Zero-bid guard shift (wing width changes)",
                 extra={"right": right, "from": strike, "to": nxt})
        strike = nxt
    return None


async def build_condor(ib: IB, vix_avg: float) -> Condor | None:
    """Full construction: deltas -> expiry -> short strikes -> wings -> priced 4-leg condor."""
    deltas = CONFIG.target_deltas(vix_avg)
    if deltas is None:
        log.warning("Systemic volatility alert: suspending entry", extra={"vix": vix_avg})
        return None
    put_dt, call_dt = deltas

    spx, spot = await spx_spot(ib)
    if not valid(spot):
        raise RuntimeError("No SPX spot (market closed / no data).")
    chain, expiry, strikes = await select_chain_and_expiry(ib, spx)

    put_short = await pick_by_delta(ib, expiry, strikes, spot, "P", put_dt, below=True)
    call_short = await pick_by_delta(ib, expiry, strikes, spot, "C", call_dt, below=False)
    if put_short is None or call_short is None:
        raise RuntimeError("Could not resolve short strikes by delta (missing greeks).")

    put_long = await zero_bid_guard(ib, expiry, strikes, put_short - CONFIG.wing_width, "P", inward=+5)
    call_long = await zero_bid_guard(ib, expiry, strikes, call_short + CONFIG.wing_width, "C", inward=-5)
    if put_long is None or call_long is None:
        raise RuntimeError("Zero-bid guard failed to find a valid long wing.")

    options = [_opt(expiry, put_short, "P"), _opt(expiry, put_long, "P"),
               _opt(expiry, call_short, "C"), _opt(expiry, call_long, "C")]
    await ib.qualifyContractsAsync(*options)

    # Halt guard across index + 4 legs.
    if await any_halted(ib, [spx, *options]):
        raise RuntimeError("Halt guard tripped: a component is halted.")

    # Net credit (positive = we receive). SELL legs add bid/ask; BUY legs subtract ask/bid.
    actions = ["SELL", "BUY", "SELL", "BUY"]
    combo_bid = combo_ask = 0.0
    for action, o in zip(actions, options):
        tkr = await ready_ticker(ib, o, want_greeks=False)
        b, a = nan_safe(tkr.bid), nan_safe(tkr.ask)
        if not (valid(a) and valid(b)):
            raise RuntimeError("Missing quote on a leg (market closed / no data).")
        if action == "SELL":
            combo_bid += b
            combo_ask += a
        else:
            combo_bid -= a
            combo_ask -= b

    condor = Condor(
        expiry=expiry, dte=dte_of(expiry), vix_avg=vix_avg,
        put_delta_tgt=put_dt, call_delta_tgt=call_dt,
        put_short=put_short, put_long=put_long, call_short=call_short, call_long=call_long,
        options=options,
        combo_bid=combo_bid, combo_ask=combo_ask,
        combo_mid=(combo_bid + combo_ask) / 2, combo_spread=abs(combo_ask - combo_bid),
    )
    log.info("Condor built", extra={
        "expiry": expiry, "dte": condor.dte, "put_short": put_short, "put_long": put_long,
        "call_short": call_short, "call_long": call_long, "credit_mid": round(condor.combo_mid, 2),
        "spread": round(condor.combo_spread, 2)})
    return condor
