"""Market-data port + a fixture-replay adapter for tests and offline dev.

``MarketData`` is the interface the ingestion module programs against. ``ReplayMarketData``
implements it from a JSON fixture so the whole pipeline runs with no vendor key — and so
backtest replay uses the exact same interface as live (README §11.2, one code path).

The live ``PolygonMarketData`` adapter (WebSocket/REST) lands here in Phase 0/1; it will
implement the same Protocol so nothing downstream changes.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from paz_rav.contracts import OptionQuote, UnderlyingQuote


@runtime_checkable
class MarketData(Protocol):
    """The only surface the system uses to obtain market data."""

    async def underlying(self, symbol: str) -> UnderlyingQuote: ...

    async def list_expiries(self, symbol: str) -> list[date]: ...

    async def chain(self, symbol: str, expiry: date) -> list[OptionQuote]: ...

    def stream(self, symbols: Iterable[str]) -> AsyncIterator[OptionQuote]:
        """Yield normalized option quotes as they arrive (live) or replay (fixture)."""
        ...


class ReplayMarketData:
    """Serves quotes from a JSON fixture. Deterministic; no network."""

    def __init__(self, fixture: str | Path):
        path = Path(fixture)
        self._data = json.loads(path.read_text(encoding="utf-8"))

    async def underlying(self, symbol: str) -> UnderlyingQuote:
        u = self._data["underlyings"][symbol]
        return UnderlyingQuote(symbol=symbol, price=u["price"], ts=datetime.fromisoformat(u["ts"]))

    async def list_expiries(self, symbol: str) -> list[date]:
        rows = self._data["chains"].get(symbol, [])
        return sorted({date.fromisoformat(r["expiry"]) for r in rows})

    async def chain(self, symbol: str, expiry: date) -> list[OptionQuote]:
        rows = self._data["chains"].get(symbol, [])
        return [OptionQuote(**r) for r in rows if date.fromisoformat(r["expiry"]) == expiry]

    async def stream(self, symbols: Iterable[str]) -> AsyncIterator[OptionQuote]:
        wanted = set(symbols)
        for sym, rows in self._data["chains"].items():
            if sym not in wanted:
                continue
            for r in rows:
                yield OptionQuote(**r)
