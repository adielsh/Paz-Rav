"""Interactive Brokers adapter — the real-time production feed.

You have a live IBKR market-data subscription, so this is the intended production source:
true real-time quotes and greeks, not delayed. It implements the same :class:`MarketData`
port as the free yfinance adapter, so switching feeds is a one-line change and nothing
downstream is affected.

Implementation notes (Phase 1):
- Talks to a running **TWS** or **IB Gateway** (the desktop app that holds your login),
  by default on ``127.0.0.1:7497`` (paper) / ``7496`` (live).
- Use ``ib_async`` (the maintained successor to ``ib_insync``): ``pip install ib_async``.
- IBKR *does* provide a genuine live stream (``reqMktData`` / ``reqTickByTickData``), so
  unlike yfinance, ``stream`` here is a real push — this is what makes live trading and
  the continuous exit-manager possible.
- Greeks come straight from IBKR's model ticks, so they can cross-check the deterministic
  ``paz_rav.quant`` values (a useful parity test).

This is a stub: the interface is fixed and correct; the wiring lands when we point the
engine at live data.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from datetime import date

from paz_rav.contracts import OptionQuote, UnderlyingQuote

_NOT_WIRED = (
    "IBKR adapter is not wired yet. Start TWS/IB Gateway, `pip install ib_async`, "
    "then implement the connection here. Use the free YFinanceMarketData adapter for now."
)


class IBKRMarketData:
    """Real-time MarketData port backed by TWS / IB Gateway (to be wired in Phase 1)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id

    async def underlying(self, symbol: str) -> UnderlyingQuote:
        raise NotImplementedError(_NOT_WIRED)

    async def list_expiries(self, symbol: str) -> list[date]:
        raise NotImplementedError(_NOT_WIRED)

    async def chain(self, symbol: str, expiry: date) -> list[OptionQuote]:
        raise NotImplementedError(_NOT_WIRED)

    async def stream(self, symbols: Iterable[str]) -> AsyncIterator[OptionQuote]:
        raise NotImplementedError(_NOT_WIRED)
        yield  # pragma: no cover  (makes this an async generator)
