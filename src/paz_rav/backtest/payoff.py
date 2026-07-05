"""Realized P&L of a structure at expiry — deterministic payoff.

Works off the same :class:`~paz_rav.strategies.base.Candidate` the builder produces, so
the backtest evaluates exactly what the live engine would trade (one code path).
"""

from __future__ import annotations

from paz_rav.strategies.base import Candidate


def leg_intrinsic(option_type: str, strike: float, terminal_price: float) -> float:
    if option_type == "call":
        return max(0.0, terminal_price - strike)
    return max(0.0, strike - terminal_price)


def pnl_at_expiry(candidate: Candidate, terminal_price: float) -> float:
    """P&L per share if held to expiry with the underlying at ``terminal_price``.

    The net credit is already collected; each long leg adds its intrinsic value and each
    short leg owes its intrinsic. Between the short strikes this returns the full credit;
    fully breached it returns -max_loss.
    """
    total = candidate.credit
    for leg in candidate.legs:
        intr = leg_intrinsic(leg.option_type, leg.strike, terminal_price)
        total += intr if leg.side == "buy" else -intr
    return round(total, 4)
