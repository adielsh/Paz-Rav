"""Free market-data adapter backed by yfinance (Yahoo).

Zero cost, no API key — perfect for building and testing the whole pipeline on real
option chains. Data is delayed (~15 min) and unofficial, so it is a *development* feed,
not a trading feed. The real-time production feed is Interactive Brokers (see
``paz_rav.adapters.ibkr``); both implement the same :class:`MarketData` port, so nothing
downstream changes when you switch.

yfinance is synchronous and network-bound, so every blocking call is pushed to a worker
thread via ``asyncio.to_thread`` — the event loop is never blocked (README §7).
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator, Iterable
from datetime import date, datetime, timezone

from paz_rav.contracts import OptionQuote, UnderlyingQuote


def _num(x) -> float | None:
    """Coerce a pandas/NumPy cell to float, mapping NaN/None to None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


class YFinanceMarketData:
    """Implements the MarketData port using Yahoo Finance (delayed, free)."""

    # Our labels -> Yahoo tickers for indices (SPX options are ^SPX on Yahoo).
    _YF = {"SPX": "^SPX", "RUT": "^RUT", "VIX": "^VIX", "NDX": "^NDX"}

    def _ticker(self, symbol: str):
        import yfinance as yf  # lazy: only needed when this adapter is actually used

        return yf.Ticker(self._YF.get(symbol.upper(), symbol))

    # -- port methods -------------------------------------------------------

    async def underlying(self, symbol: str) -> UnderlyingQuote:
        price = await asyncio.to_thread(self._blocking_price, symbol)
        return UnderlyingQuote(symbol=symbol, price=price, ts=datetime.now(timezone.utc))

    async def chain(self, symbol: str, expiry: date) -> list[OptionQuote]:
        return await asyncio.to_thread(self._blocking_chain, symbol, expiry)

    async def stream(self, symbols: Iterable[str]) -> AsyncIterator[OptionQuote]:
        """Snapshot 'stream': one pass over the nearest expiry per symbol.

        Yahoo has no live push, so this yields a current snapshot. Real streaming
        comes from the IBKR adapter. Downstream code consumes an async iterator either
        way, so it does not care which feed produced the quotes.
        """
        for sym in symbols:
            expiries = await self.list_expiries(sym)
            if not expiries:
                continue
            for q in await self.chain(sym, expiries[0]):
                yield q

    # -- helpers (beyond the port, but handy) -------------------------------

    async def list_expiries(self, symbol: str) -> list[date]:
        raw = await asyncio.to_thread(lambda: list(self._ticker(symbol).options))
        return [date.fromisoformat(s) for s in raw]

    async def nearest_expiry(self, symbol: str, target_dte: int = 45) -> date | None:
        """The listed expiry closest to ``target_dte`` calendar days out."""
        expiries = await self.list_expiries(symbol)
        if not expiries:
            return None
        today = date.today()
        return min(expiries, key=lambda e: abs((e - today).days - target_dte))

    async def recent_closes(self, symbol: str, days: int = 20) -> list[float]:
        """Recent daily closes — feeds the regime classifier's trend + RSI."""
        return await asyncio.to_thread(self._blocking_closes, symbol, days)

    async def earnings_within(self, symbol: str, days: int) -> bool:
        """Best-effort: True if an earnings report falls within ``days`` (DACS avoids these)."""
        return await asyncio.to_thread(self._blocking_earnings, symbol, days)

    def _blocking_earnings(self, symbol: str, days: int) -> bool:
        from datetime import datetime, timezone

        try:
            df = self._ticker(symbol).get_earnings_dates(limit=8)
        except Exception:
            return False
        if df is None or len(df) == 0:
            return False
        now = datetime.now(timezone.utc)
        for idx in df.index:
            try:
                dt = idx.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if 0 <= (dt - now).days <= days:
                return True
        return False

    def _blocking_closes(self, symbol: str, days: int) -> list[float]:
        hist = self._ticker(symbol).history(period=f"{max(days + 5, 10)}d")
        return [float(x) for x in hist["Close"].tolist()][-days:]

    # -- blocking implementations (run in a thread) -------------------------

    def _blocking_price(self, symbol: str) -> float:
        t = self._ticker(symbol)
        try:
            p = _num(t.fast_info["lastPrice"])
            if p:
                return p
        except Exception:
            pass
        hist = t.history(period="1d")
        return float(hist["Close"].iloc[-1])

    def _blocking_chain(self, symbol: str, expiry: date) -> list[OptionQuote]:
        t = self._ticker(symbol)
        oc = t.option_chain(expiry.isoformat())
        ts = datetime.now(timezone.utc)
        quotes: list[OptionQuote] = []
        for right, df in (("call", oc.calls), ("put", oc.puts)):
            for row in df.itertuples(index=False):
                bid = _num(getattr(row, "bid", None)) or 0.0
                ask = _num(getattr(row, "ask", None)) or 0.0
                quotes.append(
                    OptionQuote(
                        underlying=symbol,
                        right=right,
                        strike=float(row.strike),
                        expiry=expiry,
                        bid=bid,
                        ask=ask,
                        last=_num(getattr(row, "lastPrice", None)),
                        open_interest=int(_num(getattr(row, "openInterest", None)) or 0),
                        implied_vol=_num(getattr(row, "impliedVolatility", None)),
                        ts=ts,
                    )
                )
        return quotes
