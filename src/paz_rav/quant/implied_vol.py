"""Implied-volatility solver — invert Black-Scholes for sigma.

Robust bisection (no derivatives, always converges inside the bracket). Pure stdlib.
Used when the vendor doesn't supply an IV, or to cross-check one that it does.
"""

from __future__ import annotations

from paz_rav.quant.greeks import OptionType, black_scholes


def implied_vol(
    price: float, s: float, k: float, t: float, r: float,
    option_type: OptionType = "call", q: float = 0.0,
    lo: float = 1e-4, hi: float = 5.0, tol: float = 1e-8, max_iter: int = 200,
) -> float:
    """Solve ``black_scholes(sigma) == price`` for sigma via bisection.

    Raises ``ValueError`` if ``price`` is not attainable for any sigma in [lo, hi]
    (e.g. below intrinsic value or above the underlying) — the caller treats that as
    "no usable IV" rather than trusting a garbage number.
    """
    if price <= 0:
        raise ValueError("price must be positive")

    def f(sig: float) -> float:
        return black_scholes(s, k, t, r, sig, option_type, q) - price

    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        raise ValueError("price not attainable within vol bounds [lo, hi]")

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)
