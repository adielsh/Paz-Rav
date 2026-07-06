"""Walk-forward backtest: prove the edge for BOTH strategies (docs/ROADMAP.md).

Honest about the method: free real historical OPTION CHAINS don't exist, so this
simulates a chain at each cycle (Black-Scholes off a synthetic underlying path) rather
than replaying real history. The vol risk premium is real *within the simulation* in the
way that matters: options are priced at a market IV while the underlying's actual random
walk uses a lower realized vol — the same edge premium-sellers harvest live. This proves
the mechanism (deterministic core -> real, positive risk-adjusted expectancy), not a
historical return claim for any specific ticker.

Run: PYTHONPATH=src python scripts/backtest_demo.py
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, time, timedelta, timezone

from paz_rav.builder import build
from paz_rav.contracts import OptionQuote
from paz_rav.quant import black_scholes
from paz_rav.quant.valuation import structure_pnl
from paz_rav.strategies import BuildConfig, MarketContext

random.seed(7)
TODAY0 = date(2026, 1, 5)
R = 0.04


def strikes_for(spot: float) -> list[float]:
    step = 5 if spot < 300 else (10 if spot < 700 else 25)
    lo = round(spot * 0.7 / step) * step
    hi = round(spot * 1.3 / step) * step
    return [float(k) for k in range(int(lo), int(hi) + step, step)]


def make_chain(spot: float, iv: float, today: date, expiry: date) -> list[OptionQuote]:
    t = max((expiry - today).days, 1) / 365.0
    ts = datetime.combine(today, time(15, 0), tzinfo=timezone.utc)
    quotes = []
    for k in strikes_for(spot):
        for right in ("call", "put"):
            price = black_scholes(spot, k, t, R, iv, right)
            spread = max(price * 0.02, 0.01)
            quotes.append(OptionQuote(
                underlying="SIM", right=right, strike=k, expiry=expiry,
                bid=max(price - spread / 2, 0.01), ask=price + spread / 2,
                implied_vol=iv, open_interest=500, ts=ts,
            ))
    return quotes


def walk(spot: float, days: int, realized_vol: float) -> float:
    """One lognormal step of the *actual* underlying over `days`, at realized_vol."""
    t = days / 365.0
    z = random.gauss(0, 1)
    return spot * math.exp((R - 0.5 * realized_vol ** 2) * t + realized_vol * math.sqrt(t) * z)


def simulate_one(strategy: str, spot0: float, iv: float, realized_vol: float,
                 today: date, dte_front: int, dte_back: int) -> float | None:
    front = today + timedelta(days=dte_front)
    back = today + timedelta(days=dte_back)
    chains = {front: make_chain(spot0, iv, today, front),
              back: make_chain(spot0, iv, today, back)}

    cfg = BuildConfig(short_deltas=(16.0, 25.0), wing_strikes=(1, 2), max_rel_spread=1.0,
                      vrp=0.0,   # the realized/implied gap is IN the simulated path itself
                      dacs_short_dte=dte_front, dacs_gap_days=dte_back - dte_front,
                      dacs_min_fast_ratio=0.05, top_n=3)
    # Each strategy gets ITS OWN ideal regime (the "right strategy, right time" principle):
    # iron condor wants high IV rank (rich premium); DACS wants LOW IV rank + RSI~60.
    ctx = (MarketContext(regime="range / high-vol", iv_rank=70, rsi=60, earnings_soon=False)
           if strategy == "iron_condor" else
           MarketContext(regime="range / low-vol", iv_rank=25, rsi=60, earnings_soon=False))
    cands = build("SIM", spot=spot0, chains_by_expiry=chains, config=cfg, ctx=ctx,
                 today=today, strategies=[strategy])
    if not cands:
        return None
    c = cands[0]

    eval_date = date.fromisoformat(c.meta["eval_date"])
    sigma = float(c.meta.get("sigma", iv))
    terminal = walk(spot0, (eval_date - today).days, realized_vol)
    return structure_pnl(c.credit, c.legs, terminal, eval_date, R, sigma)


def summarize(pnls: list[float]) -> dict:
    if not pnls:
        return {"trades": 0}
    wins = sum(1 for p in pnls if p > 0)
    equity, peak, max_dd, running = [], 0.0, 0.0, 0.0
    for p in pnls:
        running += p
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        equity.append(round(running, 2))
    return {
        "trades": len(pnls), "wins": wins, "win_rate": wins / len(pnls),
        "avg_pnl": sum(pnls) / len(pnls), "total_pnl": sum(pnls), "max_drawdown": max_dd,
    }


# Each strategy is tested against ITS OWN appropriate universe — the honest way to
# backtest: iron condor sells premium anywhere liquid (incl. high-vol names); DACS is
# explicitly a stable/low-vol/RSI~60 play (your own rule: don't run it on volatile names).
CONDOR_ASSETS = [
    ("SPX-like", 6000.0, 0.15, 0.11),
    ("SPY-like", 100.0, 0.20, 0.15),
    ("QQQ-like", 130.0, 0.22, 0.17),
    ("Mega-cap-like", 440.0, 0.24, 0.18),
    ("Growth-like", 135.0, 0.40, 0.32),
]
DACS_ASSETS = [
    ("Stable-blue-chip-1", 60.0, 0.18, 0.13),
    ("Stable-blue-chip-2", 440.0, 0.16, 0.12),
    ("Stable-blue-chip-3", 180.0, 0.20, 0.15),
    ("Stable-index-etf", 100.0, 0.15, 0.11),
]
TRADES_PER_ASSET = 8


def main() -> None:
    for strategy, label, dte_front, dte_back, assets in (
        ("iron_condor", "IRON CONDOR", 35, 35, CONDOR_ASSETS),
        ("dacs", "DACS 1.0", 35, 65, DACS_ASSETS),
    ):
        print(f"\n=== {label} - walk-forward backtest ({len(assets)} assets x {TRADES_PER_ASSET} trades) ===")
        pnls: list[float] = []
        for name, spot0, iv, rv in assets:
            for i in range(TRADES_PER_ASSET):
                today = TODAY0 + timedelta(days=7 * i)
                pnl = simulate_one(strategy, spot0, iv, rv, today, dte_front, dte_back)
                if pnl is not None:
                    pnls.append(pnl)
        stats = summarize(pnls)
        if stats["trades"] == 0:
            print("  no trades passed the filters")
            continue
        print(f"  trades={stats['trades']}  win_rate={stats['win_rate']:.1%}  "
              f"avg_pnl={stats['avg_pnl']:+.2f}  total_pnl={stats['total_pnl']:+.2f}  "
              f"max_drawdown={stats['max_drawdown']:.2f}")
        if strategy == "dacs":
            print("  NOTE (honest limitation): this holds the position PASSIVELY to the\n"
                  "  short's expiry — no stop-loss, no early profit-take. DACS's real edge\n"
                  "  (per its own rules) is in ACTIVE management: cut at short_strike-1..-5,\n"
                  "  close early near a profit target rather than hold to expiry. A fair DACS\n"
                  "  backtest needs a day-by-day price path with those exit rules, not a single\n"
                  "  terminal-value calculation — that's real future work, not done here.")


if __name__ == "__main__":
    main()
