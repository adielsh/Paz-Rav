"""Run the analytics feature engine on REAL data (free, via yfinance).

    python scripts/analytics_demo.py SPY

Pulls the underlying + the two front expiries + recent closes, then runs the exact
`analyze()` the engine uses. IV rank shows 50 (neutral) until we have stored IV history
to rank against — that history arrives once the feature store is wired.
"""

from __future__ import annotations

import asyncio
import sys

from paz_rav.adapters import YFinanceMarketData
from paz_rav.analytics import analyze


async def main(symbol: str) -> None:
    md = YFinanceMarketData()

    spot = (await md.underlying(symbol)).price
    expiries = await md.list_expiries(symbol)
    if len(expiries) < 2:
        print(f"{symbol}: need at least two expiries")
        return

    # front ~45 DTE, plus the next listed expiry for the term-structure slope
    front = await md.nearest_expiry(symbol, 45)
    idx = expiries.index(front)
    back = expiries[min(idx + 1, len(expiries) - 1)]

    chains = {
        front: await md.chain(symbol, front),
        back: await md.chain(symbol, back),
    }
    closes = await md.recent_closes(symbol, 20)

    res = analyze(symbol, spot=spot, chains_by_expiry=chains, price_history=closes)
    f = res.feature

    print(f"{symbol}  spot={f.spot:.2f}")
    print(f"  ATM IV        {res.atm_iv:.1%}")
    print(f"  IV rank       {f.iv_rank:.0f}   (neutral until IV history is stored)")
    print(f"  term slope    {f.term_slope:+.4f}   ({front} -> {back})")
    print(f"  expected move ±{f.expected_move:.2f}")
    print(f"  skew (P-C)    {res.skew:+.1%}")
    print(f"  regime        {f.regime}")
    print(f"  condor-friendly? {res.condor_friendly}")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    asyncio.run(main(sym))
