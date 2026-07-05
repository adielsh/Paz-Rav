"""Adapters — the ports to the outside world (Adapter pattern).

The rest of the system depends on the :class:`MarketData` *port*, never on a concrete
vendor. Swapping Polygon for another provider, or replaying a fixture in tests, is a
new adapter — not a rewrite.
"""

from paz_rav.adapters.ibkr import IBKRMarketData
from paz_rav.adapters.market_data import MarketData, ReplayMarketData
from paz_rav.adapters.yfinance_md import YFinanceMarketData

__all__ = [
    "MarketData",
    "ReplayMarketData",
    "YFinanceMarketData",   # free, delayed — development feed
    "IBKRMarketData",       # real-time — production feed (you have the subscription)
]
