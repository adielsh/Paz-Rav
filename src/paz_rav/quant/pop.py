"""Probability helpers — expected move and probability of profit.

Lognormal model of the underlying at expiry under Black-Scholes assumptions.
Pure standard library. Used by the builder to score defined-risk structures.
"""

from __future__ import annotations

import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def expected_move(s: float, sigma: float, t: float) -> float:
    """One standard-deviation move of the underlying over ``t`` years.

    The desk's "expected move" — ``s * sigma * sqrt(t)``.
    """
    if s <= 0 or sigma <= 0 or t <= 0:
        raise ValueError("s, sigma, t must be positive")
    return s * sigma * math.sqrt(t)


def prob_between(
    s: float, lower: float, upper: float, sigma: float, t: float, r: float = 0.0, q: float = 0.0,
) -> float:
    """P(lower <= S_T <= upper) under the risk-neutral lognormal at expiry.

    For an iron condor this is the probability the underlying finishes between the
    short strikes' breakevens — the core of its probability of profit.
    """
    if lower >= upper:
        raise ValueError("lower must be < upper")
    if s <= 0 or sigma <= 0 or t <= 0:
        raise ValueError("s, sigma, t must be positive")
    vol_sqrt_t = sigma * math.sqrt(t)
    drift = (r - q - 0.5 * sigma * sigma) * t

    def _cdf_at(level: float) -> float:
        if level <= 0:
            return 0.0
        d = (math.log(level / s) - drift) / vol_sqrt_t
        return _norm_cdf(d)

    return _cdf_at(upper) - _cdf_at(lower)


def prob_of_profit(
    s: float, breakevens: tuple[float, ...], sigma: float, t: float,
    *, profit_region: str = "between", r: float = 0.0, q: float = 0.0,
) -> float:
    """Probability of profit given a structure's breakeven(s).

    - ``between`` (condor / short strangle): profit if lower_be <= S_T <= upper_be.
    - ``outside`` (long strangle): profit if S_T < lower_be or S_T > upper_be.
    """
    if profit_region == "between":
        if len(breakevens) != 2:
            raise ValueError("'between' needs exactly two breakevens")
        lower, upper = sorted(breakevens)
        return prob_between(s, lower, upper, sigma, t, r, q)
    if profit_region == "outside":
        if len(breakevens) != 2:
            raise ValueError("'outside' needs exactly two breakevens")
        lower, upper = sorted(breakevens)
        return 1.0 - prob_between(s, lower, upper, sigma, t, r, q)
    raise ValueError(f"unknown profit_region: {profit_region!r}")
