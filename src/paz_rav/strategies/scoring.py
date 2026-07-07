"""Shared candidate finalization + regime fit.

Every strategy is scored the same way — **risk-adjusted expected P&L times a regime
fit** — so an iron condor and a double diagonal can be ranked against each other fairly.
The grid ("digital twin") supplies POP and expected P&L for any structure.
"""

from __future__ import annotations

from datetime import date

from paz_rav.quant.valuation import grid_stats
from paz_rav.strategies.base import Candidate, Leg, MarketContext


def condor_fit(ctx: MarketContext) -> float:
    """Iron condors want range-bound + high IV (sell rich premium)."""
    f = 1.0
    f *= 1.25 if ctx.regime.startswith("range") else 0.6
    f *= 1.25 if ctx.iv_rank >= 50 else 0.75
    return round(f, 3)


def calendar_fit(ctx: MarketContext) -> float:
    """Diagonals are long vega: they prefer range-bound + LOW IV (buy vol cheap)."""
    f = 1.0
    f *= 1.25 if ctx.regime.startswith("range") else 0.7
    f *= 1.25 if ctx.iv_rank < 50 else 0.75
    return round(f, 3)


def dacs_fit(ctx: MarketContext) -> float:
    """DACS wants a stable name: RSI ~60, LOW IV, range-bound, and NO near earnings."""
    if ctx.earnings_soon:
        return 0.0                                   # hard skip: earnings can spike the short
    f = 1.0
    f *= 1.3 if ctx.iv_rank < 50 else 0.6            # high IV is bad for us
    f *= 1.15 if ctx.regime.startswith("range") else 0.85
    if ctx.rsi is not None:                          # closeness to RSI 60
        dist = abs(ctx.rsi - 60)
        f *= 1.25 if dist <= 10 else (0.9 if dist <= 20 else 0.55)
    return round(f, 3)


def finalize(
    *, underlying: str, strategy: str, legs: list[Leg], entry_credit: float,
    spot: float, eval_date: date, sigma: float, today: date, regime_fit: float,
    r: float = 0.04, width: float = 0.0, vrp: float = 0.0,
    max_loss: float | None = None, max_profit: float | None = None,
    breakevens: tuple[float, ...] | None = None,
) -> Candidate:
    """Price a structure on the grid and package a ranked Candidate.

    ``vrp`` is the volatility risk premium: the grid's realized vol is ``sigma*(1-vrp)``,
    so selling premium at the market IV carries positive expectancy — the condor's edge.
    Analytic overrides (``max_loss`` etc.) are used for closed-form structures (condor).
    """
    legs_t = tuple(legs)
    realized = sigma * (1.0 - vrp)
    gs = grid_stats(entry_credit, legs_t, spot, eval_date, sigma, today, r, realized_vol=realized)
    ml = max_loss if max_loss is not None else gs.max_loss
    mp = max_profit if max_profit is not None else gs.max_profit
    be = breakevens if breakevens is not None else gs.breakevens

    ror = gs.expected_pnl / ml if ml and ml > 1e-9 else 0.0   # risk-adjusted expectancy
    score = round(ror * regime_fit, 6)

    return Candidate(
        underlying=underlying,
        strategy=strategy,
        dte=(eval_date - today).days,
        legs=legs_t,
        credit=round(entry_credit, 2),
        width=round(width, 2),
        max_profit=round(mp, 2),
        max_loss=round(ml, 2),
        breakevens=tuple(round(b, 2) for b in be),
        pop=gs.pop,
        score=score,
        meta={"regime_fit": regime_fit, "expected_pnl": gs.expected_pnl,
              "ror": round(ror, 4), "eval_date": eval_date.isoformat(),
              "sigma": round(sigma, 4), "spot": round(spot, 2)},
    )
