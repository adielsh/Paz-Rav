"""End-to-end deterministic pipeline on REAL data (free, via yfinance).

    python scripts/builder_demo.py SPY

fetch chain -> analytics regime -> builder enumerates & ranks real iron condors.
This is the whole Phase-1 core, no AI, every number computed.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date

from paz_rav.adapters import YFinanceMarketData
from paz_rav.analytics import analyze
from paz_rav.builder import build
from paz_rav.strategies import BuildConfig


async def main(symbol: str) -> None:
    md = YFinanceMarketData()

    spot = (await md.underlying(symbol)).price
    expiry = await md.nearest_expiry(symbol, target_dte=45)
    if expiry is None:
        print(f"{symbol}: no listed expiries")
        return
    dte = (expiry - date.today()).days
    chain = await md.chain(symbol, expiry)
    closes = await md.recent_closes(symbol, 20)

    res = analyze(symbol, spot=spot, chains_by_expiry={expiry: chain}, price_history=closes)
    print(f"{symbol}  spot={spot:.2f}  expiry={expiry} ({dte} DTE)  "
          f"regime={res.feature.regime}  condor-friendly={res.condor_friendly}\n")

    cfg = BuildConfig(short_deltas=(16.0, 25.0), wing_widths=(5.0, 10.0),
                      min_open_interest=10, max_rel_spread=0.6, top_n=6)
    candidates = build(symbol, spot=spot, dte=dte, quotes=chain, config=cfg)

    if not candidates:
        print("no candidates passed the liquidity filter (try during market hours).")
        return

    print(f"{'#':>2}  {'short put / call':>16}  {'width':>5}  {'credit':>6}  "
          f"{'maxloss':>7}  {'POP':>5}  {'score':>6}")
    for i, c in enumerate(candidates, 1):
        shorts = sorted(leg.strike for leg in c.legs if leg.side == "sell")
        print(f"{i:>2}  {shorts[0]:>7.0f} /{shorts[1]:>6.0f}  {c.width:>5.0f}  "
              f"{c.credit:>6.2f}  {c.max_loss:>7.2f}  {c.pop:>5.1%}  {c.score:>6.4f}")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    asyncio.run(main(sym))
