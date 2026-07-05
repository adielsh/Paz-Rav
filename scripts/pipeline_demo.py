"""The full Phase-1 pipeline on REAL data (free yfinance) with in-memory stores + bus.

    python scripts/pipeline_demo.py SPY

Runs the wired loop twice to show IV history accumulating (which powers IV rank) and
that features + candidates are stored and published — the whole deterministic engine.
"""

from __future__ import annotations

import asyncio
import sys

from paz_rav.adapters import YFinanceMarketData
from paz_rav.bus import CH_CANDIDATES, CH_FEATURES, InMemoryBus
from paz_rav.pipeline import Pipeline
from paz_rav.store.memory import (
    InMemoryCandidateRepository,
    InMemoryFeatureStore,
    InMemoryIVHistory,
)
from paz_rav.strategies import BuildConfig


async def main(symbol: str) -> None:
    p = Pipeline(
        md=YFinanceMarketData(),
        feature_store=InMemoryFeatureStore(),
        iv_history=InMemoryIVHistory(),
        candidate_repo=InMemoryCandidateRepository(),
        bus=InMemoryBus(),
        config=BuildConfig(short_deltas=(16.0, 25.0), wing_widths=(5.0, 10.0),
                           min_open_interest=10, max_rel_spread=0.6, top_n=5),
    )

    result = await p.run_once(symbol)
    if result is None:
        print(f"{symbol}: no data")
        return

    f = result.feature
    print(f"{symbol}  spot={f.spot:.2f}  regime={f.regime}  IVrank={f.iv_rank:.0f}  "
          f"exp.move=±{f.expected_move:.2f}\n")
    print(f"{'#':>2}  {'short put/call':>15}  {'width':>5}  {'credit':>6}  {'POP':>5}  {'score':>6}")
    for i, c in enumerate(result.candidates, 1):
        s = sorted(leg.strike for leg in c.legs if leg.side == "sell")
        print(f"{i:>2}  {s[0]:>7.0f}/{s[1]:>6.0f}  {c.width:>5.0f}  {c.credit:>6.2f}  "
              f"{c.pop:>5.1%}  {c.score:>6.4f}")

    # second pass — IV history grows, feeding real IV rank over time
    await p.run_once(symbol)
    hist = await p.iv_history.window(symbol, 365)
    print(f"\nstored: feature={await p.feature_store.get(symbol) is not None}  "
          f"candidates={len(await p.candidate_repo.latest(symbol))}  "
          f"IV-history-points={len(hist)}")
    print(f"published: features={len(p.bus.published.get(CH_FEATURES, []))}  "
          f"candidates={len(p.bus.published.get(CH_CANDIDATES, []))}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "SPY"))
