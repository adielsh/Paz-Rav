"""One-off, READ-ONLY probe of the combo price sign convention.

Builds a real SPXW condor from live data, then asks IBKR to price BOTH formulations with
whatIfOrderAsync:

    A) BUY  @ NEGATIVE limit   <- what execution.py does today
    B) SELL @ POSITIVE limit   <- the opposite reading

whatIf orders are never transmitted — IBKR only returns the projected margin/equity impact.
For a defined-risk credit condor the correct opening order should show an init-margin add of
roughly (wing_width - credit) * multiplier * lots, and should NOT reduce equity-with-loan by
the notional of a long position.

Run:  docker exec condor-core python -m app.verify_sign
"""
from __future__ import annotations

import asyncio
import os

from ib_async import IB

from .config import CONFIG
from .data_fetcher import connect, vix_average, build_condor
from .risk_manager import build_bag
from .execution import _combo_order
from .utils import round_to_tick


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _show(tag: str, what) -> dict:
    keys = ["initMarginBefore", "initMarginAfter", "initMarginChange",
            "maintMarginChange", "equityWithLoanChange", "commission", "warningText"]
    out = {k: getattr(what, k, None) for k in keys}
    print(f"\n--- {tag}")
    for k in keys:
        print(f"    {k:22} {out[k]}")
    return out


async def main() -> None:
    ib = IB()
    # A dedicated clientId so we never disturb the daemon (11) or the API bridge (12-23).
    CONFIG_ID = int(os.getenv("PROBE_CLIENT_ID", "31"))
    await ib.connectAsync(CONFIG.ib_host, CONFIG.ib_port, clientId=CONFIG_ID, timeout=20)
    ib.reqMarketDataType(CONFIG.market_data_type)
    acct = (ib.managedAccounts() or [""])[0]
    print(f"connected  account={acct}  lots={CONFIG.lot_size}  "
          f"market_data_type={CONFIG.market_data_type}")

    vix = await vix_average(ib)
    condor = await build_condor(ib, vix)
    if condor is None:
        print("VIX regime says suspend — no condor to probe.")
        return

    credit = round_to_tick(condor.combo_mid)
    width = condor.put_short - condor.put_long
    expected = (width - credit) * CONFIG.multiplier * CONFIG.lot_size
    print(f"\ncondor     {condor.expiry}  {condor.put_long}/{condor.put_short}"
          f" - {condor.call_short}/{condor.call_long}")
    print(f"credit mid {credit}   wing width {width}")
    print(f"EXPECTED init-margin add for a credit condor ~ {expected:,.0f}")

    bag = build_bag(condor.options)

    a = await ib.whatIfOrderAsync(bag, _combo_order("BUY", -credit, tif="DAY"))
    A = _show("A) BUY @ -{:.2f}   (current convention)".format(credit), a)

    b = await ib.whatIfOrderAsync(bag, _combo_order("SELL", credit, tif="DAY"))
    B = _show("B) SELL @ +{:.2f}  (opposite reading)".format(credit), b)

    print("\n================ VERDICT ================")
    for tag, r in (("A (BUY @ negative)", A), ("B (SELL @ positive)", B)):
        add = _f(r["initMarginChange"])
        ewl = _f(r["equityWithLoanChange"])
        fit = abs(add - expected) / expected if expected else float("nan")
        print(f"{tag:22} margin_add={add:>12,.0f}  ewl_change={ewl:>12,.0f}  "
              f"off_by={fit*100:>6.1f}%")
    print("\nThe formulation whose margin_add is closest to the expected defined risk is the")
    print("one that actually OPENS the condor for a credit.")
    ib.disconnect()


if __name__ == "__main__":
    from ib_async import util
    util.run(main())
