"""Interactive Brokers adapter — quotes from the same broker the daemon trades through.

Implements the :class:`~paz_rav.adapters.market_data.MarketData` port against a running
TWS / IB Gateway via ``ib_async``, so switching feeds is a config change and nothing
downstream is affected.

Why this matters more than "it's live data": the console's daemon
(``apps/console/trading-core``) already prices and executes through this gateway. Until
now the engine ranked candidates off yfinance — a *different vendor*, delayed, with
chains that need not agree strike-for-strike with what IBKR would actually fill. Sharing
one source is what makes an engine idea and a broker order comparable at all.

**It does not fetch greeks.** The builder computes its own delta/IV from the quote
(``builder.annotate`` → ``analytics.iv.contract_iv`` → ``quant.greeks``), which keeps the
project's rule that every number is computed in deterministic Python. IBKR's model IV is
requested anyway, because it rides free on the same subscription and saves the solver a
guess; it is used only as an input to that same deterministic path.

**The market-data line budget is the real constraint here, not correctness.** IBKR caps
concurrent market-data lines (~100 per login) and *the daemon that actually places orders
shares that cap*. Exhausting it does not raise — requests just silently return nothing,
which would degrade live trading to protect a ranking engine. So this adapter:

- opens at most ``max_lines`` subscriptions at once (default 32, deliberately far below
  the cap, leaving the daemon room),
- always cancels a line in ``finally``, even on timeout,
- and reads a ``moneyness`` band around spot thinned to ``strikes_each_side`` per side,
  rather than the whole chain, which is what makes a scan bounded at all.

Even so, IBKR cannot sustain the engine's default shape — nine underlyings, two expiries,
every 60 seconds. Run a short ``UNDERLYINGS`` list and a longer ``PAZ_SCAN_INTERVAL``
when using this feed, or keep yfinance for breadth and use this for the names you would
really trade.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable
from datetime import date, datetime, timezone

from paz_rav.contracts import OptionQuote, UnderlyingQuote

log = logging.getLogger("paz_rav.adapters.ibkr")

#: Cash indices are ``Index`` contracts on their own exchange; everything else is a
#: SMART-routed stock/ETF. Getting this wrong yields an unqualified contract, not an error.
_INDEX_EXCHANGE = {"SPX": "CBOE", "VIX": "CBOE", "NDX": "NASDAQ", "RUT": "RUSSELL",
                   "DJX": "CBOE", "XSP": "CBOE"}

#: Generic ticks: 100 = option volume, 101 = option open interest, 106 = option implied
#: vol. All three ride on one subscription, so they cost no extra lines.
_GENERIC_TICKS = "100,101,106"


def _pick_chain(chains, symbol: str):
    """Choose the right option class out of everything ``reqSecDefOptParamsAsync`` returns.

    This is not a formality. IBKR answers with several classes per underlying — for SPY it
    returns ``2SPY`` (an adjusted/mini class with a sparse ladder and two expiries)
    alongside the real ``SPY``. Taking the first SMART entry picked ``2SPY``, and every
    strike then came back *"No security definition has been found"*: a chain that looked
    empty rather than wrong.

    Order: the PM-settled weeklies when they exist (``SPXW`` — what the console's daemon
    actually trades), else the class named exactly after the symbol, else whatever is
    SMART-routed. Ties break on the most complete ladder, which is what separates the real
    class from an adjusted one.
    """
    sym = symbol.upper()
    smart = [c for c in chains if c.exchange == "SMART"] or list(chains)
    pool = ([c for c in smart if c.tradingClass == f"{sym}W"]
            or [c for c in smart if c.tradingClass == sym]
            or smart)
    return max(pool, key=lambda c: (len(c.strikes), len(c.expirations)))


def _thin(seq: list[float], n: int) -> list[float]:
    """At most `n` items spread evenly across `seq`, always keeping both ends.

    Truncating instead would drop exactly the far strikes the delta targets live at.
    """
    if n <= 0 or not seq:
        return []
    if len(seq) <= n:
        return list(seq)
    step = (len(seq) - 1) / (n - 1) if n > 1 else 0
    picked = sorted({int(round(i * step)) for i in range(n)})
    return [seq[i] for i in picked]


def _is_nan(x) -> bool:
    return x is None or x != x


def _num(x) -> float | None:
    """IBKR uses NaN for 'no value'. Normalise to None so pydantic sees a real absence."""
    if _is_nan(x):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v < 0 else v


class IBKRMarketData:
    """Real-time (or delayed) MarketData port backed by TWS / IB Gateway."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        client_id: int = 25,
        *,
        market_data_type: int = 3,
        max_lines: int = 32,
        strikes_each_side: int = 18,
        moneyness: float = 0.12,
        quote_timeout: float = 6.0,
        connect_timeout: float = 20.0,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.market_data_type = market_data_type
        self.max_lines = max_lines
        self.strikes_each_side = strikes_each_side
        self.moneyness = moneyness
        # Ceiling on how many strikes we ask IBKR to *define* per expiry. Costs no
        # market-data lines, only a definition lookup, so it can be far above the quote
        # budget -- generous enough that a coarse ladder still yields enough listed
        # strikes to thin down from.
        self._qualify_cap = max(strikes_each_side * 6, 60)
        self.quote_timeout = quote_timeout
        self.connect_timeout = connect_timeout
        # A POOL, not one id — see _connect. Sized to outlast a few restarts, and kept
        # clear of the console's ids (its daemon holds 11, its API rotates 12-23).
        self._client_ids = list(range(client_id, client_id + 10))
        self._ci = 0
        self._ib = None
        self._lock = asyncio.Lock()
        # reqSecDefOptParamsAsync is slow and its answer (expiries, strike ladder) changes
        # daily at most, while a scan asks for it once per underlying per pass.
        self._params: dict[str, tuple[date, object]] = {}

    # ---------------------------------------------------------------- connection --

    async def _connect(self):
        """Lazy, serialised connect on a FRESH IB() with a ROTATING clientId.

        Reusing one clientId looks correct and fails in production. When this container
        restarts, the gateway can still hold the previous session under that id; the new
        connect then either hangs the handshake or succeeds but returns empty quotes
        forever — indistinguishable from "no market-data subscription". Observed exactly
        that: every symbol failed until a fresh id was used.

        The console's ib_bridge already solved this the same way (it rotates 12-23), so
        this is the house pattern, not an invention.
        """
        from ib_async import IB

        async with self._lock:
            if self._ib is not None and self._ib.isConnected():
                return self._ib
            if self._ib is not None:
                try:
                    self._ib.disconnect()
                except Exception:
                    pass
            cid = self._client_ids[self._ci % len(self._client_ids)]
            self._ci += 1
            ib = IB()
            await asyncio.wait_for(
                ib.connectAsync(self.host, self.port, clientId=cid,
                                timeout=self.connect_timeout),
                timeout=self.connect_timeout + 5,
            )
            self.client_id = cid
            # Without this, an account with no live subscription returns empty quotes
            # rather than falling back to delayed on its own.
            ib.reqMarketDataType(self.market_data_type)
            self._ib = ib
            log.info("IBKR connected host=%s port=%s clientId=%s market_data_type=%s",
                     self.host, self.port, self.client_id, self.market_data_type)
            if self.market_data_type != 1:
                log.warning("Delayed IBKR data in use — quotes lag ~15 minutes and are NOT "
                            "execution-grade")
            return ib

    async def close(self) -> None:
        if self._ib is not None:
            try:
                self._ib.disconnect()
            except Exception:
                pass
            self._ib = None

    # -------------------------------------------------------------------- quotes --

    def _underlying_contract(self, symbol: str):
        from ib_async import Index, Stock

        exch = _INDEX_EXCHANGE.get(symbol.upper())
        if exch:
            return Index(symbol.upper(), exch)
        return Stock(symbol.upper(), "SMART", "USD")

    async def _ready(self, ib, contract, timeout: float | None = None):
        """Subscribe until a usable quote appears, then ALWAYS release the line.

        A held line is the failure mode that matters: IBKR silently returns nothing once
        the cap is hit, so a leak here would degrade the trading daemon rather than raise.
        """
        timeout = self.quote_timeout if timeout is None else timeout
        ticker = ib.reqMktData(contract, _GENERIC_TICKS, False, False)
        try:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + timeout
            while loop.time() < deadline:
                await asyncio.sleep(0.2)
                # `close` counts: outside RTH (and on holidays) there is no live book, but
                # the previous close still prices the chain well enough to rank it.
                if not _is_nan(ticker.bid) or not _is_nan(ticker.ask) \
                        or not _is_nan(ticker.last) or not _is_nan(ticker.close):
                    break
            return ticker
        finally:
            try:
                ib.cancelMktData(contract)
            except Exception:
                pass

    async def underlying(self, symbol: str) -> UnderlyingQuote:
        ib = await self._connect()
        c = self._underlying_contract(symbol)
        await ib.qualifyContractsAsync(c)
        if not c.conId:
            raise RuntimeError(f"IBKR could not qualify underlying {symbol!r}")
        t = await self._ready(ib, c)
        price = _num(t.last) or _num(t.close) or _num(t.marketPrice())
        if not price:
            raise RuntimeError(f"No price for {symbol!r} from IBKR (no subscription, or "
                               f"the market has never opened for this contract)")
        return UnderlyingQuote(symbol=symbol.upper(), price=price,
                               ts=datetime.now(timezone.utc))

    # --------------------------------------------------------------------- chain --

    async def _chain_params(self, ib, symbol: str):
        """(expirations, strikes, tradingClass) for `symbol`, cached for the day."""
        today = date.today()
        hit = self._params.get(symbol.upper())
        if hit and hit[0] == today:
            return hit[1]

        c = self._underlying_contract(symbol)
        await ib.qualifyContractsAsync(c)
        if not c.conId:
            raise RuntimeError(f"IBKR could not qualify underlying {symbol!r}")
        sec_type = "IND" if symbol.upper() in _INDEX_EXCHANGE else "STK"
        chains = await ib.reqSecDefOptParamsAsync(c.symbol, "", sec_type, c.conId)
        if not chains:
            raise RuntimeError(f"IBKR returned no option chain for {symbol!r}")
        chain = _pick_chain(chains, symbol)
        log.info("IBKR chain params %s: tradingClass=%s exchange=%s (%d strikes, %d expiries)",
                 symbol, chain.tradingClass, chain.exchange,
                 len(chain.strikes), len(chain.expirations))
        params = (sorted(chain.expirations), sorted(chain.strikes), chain.tradingClass)
        self._params[symbol.upper()] = (today, params)
        return params

    async def list_expiries(self, symbol: str) -> list[date]:
        ib = await self._connect()
        expirations, _, _ = await self._chain_params(ib, symbol)
        out = []
        for e in expirations:
            try:
                out.append(datetime.strptime(e, "%Y%m%d").date())
            except ValueError:      # IBKR occasionally returns a YYYYMM form
                continue
        return sorted(out)

    async def chain(self, symbol: str, expiry: date) -> list[OptionQuote]:
        ib = await self._connect()
        spot = (await self.underlying(symbol)).price
        _, strikes, trading_class = await self._chain_params(ib, symbol)
        band = self._band(strikes, spot)
        if not band:
            return []

        from ib_async import Option

        # Qualify FIRST, thin AFTER. `qualifyContractsAsync` is a contract-definition
        # lookup: it costs no market-data lines, unlike reqMktData. Thinning before
        # qualifying spent the whole budget on strikes that turned out not to exist --
        # SPX advertises a 744-strike ladder spanning every expiry, but any single weekly
        # lists only a coarse subset of it, so an evenly-thinned band qualified 2 of 6 and
        # the scan produced nothing. Qualifying generously and thinning the SURVIVORS
        # spends the budget only on contracts that are really listed.
        ymd = expiry.strftime("%Y%m%d")
        probe = [Option(symbol.upper(), ymd, k, r, "SMART", tradingClass=trading_class)
                 for k in _thin(band, self._qualify_cap) for r in ("P", "C")]
        await ib.qualifyContractsAsync(*probe)
        listed = sorted({c.strike for c in probe if c.conId})
        if not listed:
            log.warning("No strikes qualified for %s %s", symbol, expiry)
            return []

        keep = set(self._per_side(listed, spot))
        contracts = [c for c in probe if c.conId and c.strike in keep]
        quotes = await self._quote_all(ib, contracts)
        log.info("IBKR chain %s %s: band=%d probed=%d listed=%d quoted=%d -> %d quotes",
                 symbol, expiry, len(band), len(probe), len(listed),
                 len(contracts), len(quotes))
        return quotes

    def _band(self, strikes: list[float], spot: float) -> list[float]:
        """Every advertised strike within ±`moneyness` of spot.

        A percentage band, not a count of the nearest strikes: 18 strikes each side of a
        $769 spot reaches only ±2.3%, and a 16-delta short strike at 35 DTE sits well
        outside that — the chain came back bounded, valid and useless. The band gives the
        reach; `_per_side` supplies the bound, after qualification.
        """
        lo, hi = spot * (1.0 - self.moneyness), spot * (1.0 + self.moneyness)
        return [k for k in strikes if lo <= k <= hi]

    def _per_side(self, listed: list[float], spot: float) -> list[float]:
        """Thin the LISTED strikes to `strikes_each_side` each side, spread evenly."""
        below = [k for k in listed if k <= spot]
        above = [k for k in listed if k > spot]
        return _thin(below, self.strikes_each_side) + _thin(above, self.strikes_each_side)

    async def _quote_all(self, ib, contracts) -> list[OptionQuote]:
        """Quote every contract, at most `max_lines` subscriptions open at any moment."""
        sem = asyncio.Semaphore(self.max_lines)
        now = datetime.now(timezone.utc)
        out: list[OptionQuote] = []

        async def one(c):
            async with sem:
                try:
                    t = await self._ready(ib, c)
                except Exception as e:              # one bad contract must not kill a scan
                    log.debug("quote failed for %s %s: %s", c.strike, c.right, e)
                    return
            bid, ask = _num(t.bid), _num(t.ask)
            last = _num(t.last) or _num(t.close)
            if bid is None and ask is None and last is None:
                return                              # nothing usable; drop rather than invent
            oi = _num(t.putOpenInterest if c.right == "P" else t.callOpenInterest)
            iv = None
            if t.modelGreeks is not None:
                iv = _num(getattr(t.modelGreeks, "impliedVol", None))
            out.append(OptionQuote(
                underlying=c.symbol,
                right="put" if c.right == "P" else "call",
                strike=float(c.strike),
                expiry=datetime.strptime(c.lastTradeDateOrContractMonth, "%Y%m%d").date(),
                # A one-sided book is normal off-hours; 0.0 keeps `mid` honest and the
                # builder falls back to `last`, rather than us fabricating the other side.
                bid=bid or 0.0,
                ask=ask or 0.0,
                last=last,
                open_interest=int(oi) if oi is not None else None,
                implied_vol=iv,
                ts=now,
            ))

        await asyncio.gather(*(one(c) for c in contracts))
        out.sort(key=lambda q: (q.expiry, q.strike, q.right))
        return out

    async def stream(self, symbols: Iterable[str]) -> AsyncIterator[OptionQuote]:
        """Snapshot, not a push feed — matching the yfinance adapter's behaviour.

        A true `reqTickByTickData` stream is possible here and is the thing IBKR offers
        that yfinance cannot, but nothing in the pipeline consumes `stream()` today, so
        implementing one would be an untested line budget running permanently.
        """
        for sym in symbols:
            expiries = await self.list_expiries(sym)
            if not expiries:
                continue
            for q in await self.chain(sym, expiries[0]):
                yield q
