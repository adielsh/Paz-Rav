"""Pull a REAL option chain (free, via yfinance) and build an iron condor from it.

Proves the whole deterministic path on live-ish data, no API key, no paid feed:

    python scripts/fetch_demo.py SPY

Steps: pick the expiry nearest 45 DTE -> fetch the chain -> choose ~16-delta short
strikes with $5 wings -> price the condor with paz_rav.strategies. Everything after the
fetch is the same code the engine uses.
"""

from __future__ import annotations

import asyncio
import sys

from paz_rav.adapters import YFinanceMarketData
from paz_rav.strategies import make_strategy


def _nearest(strikes: list[float], target: float) -> float:
    return min(strikes, key=lambda s: abs(s - target))


async def main(symbol: str) -> None:
    md = YFinanceMarketData()

    spot = (await md.underlying(symbol)).price
    expiry = await md.nearest_expiry(symbol, target_dte=45)
    if expiry is None:
        print(f"no listed expiries for {symbol}")
        return
    dte = (expiry - __import__("datetime").date.today()).days
    chain = await md.chain(symbol, expiry)

    print(f"{symbol}: spot={spot:.2f}  expiry={expiry} ({dte} DTE)  contracts={len(chain)}")

    calls = sorted({q.strike for q in chain if q.right == "call"})
    puts = sorted({q.strike for q in chain if q.right == "put"})
    if not calls or not puts:
        print("chain missing a side; try another symbol/expiry")
        return

    # ~1 expected-move-ish OTM shorts (rough: 5% out), $5 wings.
    short_put = _nearest(puts, spot * 0.95)
    long_put = _nearest(puts, short_put - 5)
    short_call = _nearest(calls, spot * 1.05)
    long_call = _nearest(calls, short_call + 5)

    # net credit from mids
    def mid(right: str, strike: float) -> float:
        for q in chain:
            if q.right == right and q.strike == strike:
                return q.mid
        return 0.0

    credit = (mid("put", short_put) - mid("put", long_put)
              + mid("call", short_call) - mid("call", long_call))

    # a representative IV for POP (use the short put's, fall back to 0.20)
    iv = next((q.implied_vol for q in chain
               if q.right == "put" and q.strike == short_put and q.implied_vol), 0.20)

    if credit <= 0:
        print(f"strikes {long_put}/{short_put}/{short_call}/{long_call}: non-positive credit "
              f"({credit:.2f}) from delayed quotes — try during market hours.")
        return

    condor = make_strategy("iron_condor").build(
        underlying=symbol, spot=spot, dte=dte,
        put_long=long_put, put_short=short_put,
        call_short=short_call, call_long=long_call,
        credit=round(credit, 2), sigma=iv,
    )
    print(f"strikes: {long_put}/{short_put}  ...  {short_call}/{long_call}")
    print(f"credit={condor.credit:.2f}  width={condor.width}  max_loss={condor.max_loss:.2f}  "
          f"POP={condor.pop:.1%}  score={condor.score:.4f}")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    asyncio.run(main(sym))
