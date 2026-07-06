"""General structure valuation — the deterministic 'digital twin'.

Values ANY multi-leg, multi-expiry structure at an evaluation date and integrates over
the lognormal distribution of the underlying to get probability of profit, expected P&L,
and breakevens. Iron condors (single expiry -> intrinsic) and diagonals (long legs still
alive -> priced with Black-Scholes) go through the same code.

Assumption (honest): legs still alive at the evaluation date are priced at their entry
IV held constant. A full vol-path model is a later refinement; this is a sound first cut
and is exactly the kind of number the committee (Phase 2) would stress-test.
"""

from __future__ import annotations

import math
from datetime import date

from paz_rav.quant.greeks import black_scholes
from paz_rav.strategies.base import Leg


def _intrinsic(option_type: str, strike: float, s: float) -> float:
    return max(0.0, s - strike) if option_type == "call" else max(0.0, strike - s)


def leg_value(leg: Leg, s: float, eval_date: date, r: float, default_iv: float) -> float:
    """Value of one leg at ``eval_date`` for underlying ``s`` (signed: + long, - short)."""
    expiry = leg.expiry or eval_date
    t_left = max((expiry - eval_date).days, 0) / 365.0
    iv = leg.iv if (leg.iv and leg.iv > 0) else default_iv
    if t_left <= 0 or iv <= 0:
        price = _intrinsic(leg.option_type, leg.strike, s)
    else:
        price = black_scholes(s, leg.strike, t_left, r, iv, leg.option_type)
    signed = price if leg.side == "buy" else -price
    return signed * leg.quantity


def structure_pnl(
    entry_credit: float, legs: tuple[Leg, ...], s: float, eval_date: date,
    r: float, default_iv: float,
) -> float:
    """P&L per share at ``eval_date`` for underlying ``s``.

    ``entry_credit`` is the net cash taken in at open (negative for a net debit). The
    position's liquidation value at eval is added: long legs worth +price, shorts -price.
    """
    return entry_credit + sum(leg_value(leg, s, eval_date, r, default_iv) for leg in legs)


class GridStats:
    __slots__ = ("pop", "expected_pnl", "max_profit", "max_loss", "breakevens")

    def __init__(self, pop, expected_pnl, max_profit, max_loss, breakevens):
        self.pop = pop
        self.expected_pnl = expected_pnl
        self.max_profit = max_profit
        self.max_loss = max_loss
        self.breakevens = breakevens


def grid_stats(
    entry_credit: float, legs: tuple[Leg, ...], spot: float, eval_date: date,
    sigma: float, today: date, r: float = 0.04, *, n: int = 201, width: float = 4.0,
) -> GridStats:
    """POP, expected P&L, max profit/loss and breakevens via lognormal integration.

    The underlying at ``eval_date`` is lognormal with vol ``sigma`` over the horizon
    today->eval_date. We scan ``n`` price points spanning ``±width`` sigma in log-space,
    weight each by the lognormal density, and evaluate ``structure_pnl`` at each.
    """
    t = max((eval_date - today).days, 1) / 365.0
    sig_sqrt_t = max(sigma, 1e-6) * math.sqrt(t)
    mu = math.log(spot) + (r - 0.5 * sigma * sigma) * t

    ln_lo, ln_hi = math.log(spot) - width * sig_sqrt_t, math.log(spot) + width * sig_sqrt_t
    step = (ln_hi - ln_lo) / (n - 1)

    prices, pnls, weights = [], [], []
    for i in range(n):
        ln_s = ln_lo + i * step
        s = math.exp(ln_s)
        w = math.exp(-0.5 * ((ln_s - mu) / sig_sqrt_t) ** 2)
        prices.append(s)
        pnls.append(structure_pnl(entry_credit, legs, s, eval_date, r, sigma))
        weights.append(w)

    tot_w = sum(weights) or 1.0
    pop = sum(w for w, p in zip(weights, pnls) if p > 0) / tot_w
    expected_pnl = sum(w * p for w, p in zip(weights, pnls)) / tot_w
    max_profit = max(pnls)
    max_loss = -min(pnls)  # positive number; the worst outcome on the grid

    breakevens: list[float] = []
    for i in range(1, n):
        a, b = pnls[i - 1], pnls[i]
        if (a <= 0 < b) or (a >= 0 > b):
            frac = a / (a - b) if a != b else 0.0
            breakevens.append(round(prices[i - 1] + frac * (prices[i] - prices[i - 1]), 2))

    return GridStats(round(pop, 4), round(expected_pnl, 4),
                     round(max_profit, 4), round(max_loss, 4), tuple(breakevens))
