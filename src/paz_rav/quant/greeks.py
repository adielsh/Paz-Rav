"""Black-Scholes price and greeks — pure standard library.

Deterministic and dependency-free so it is trivially testable. Values are validated
against py_vollib in the parity tests when the optional `quant` extra is installed.

Conventions
-----------
- ``s``     spot price of the underlying
- ``k``     strike
- ``t``     time to expiry in years (e.g. 45 DTE -> 45/365)
- ``r``     risk-free rate (annual, continuous), e.g. 0.04
- ``sigma`` implied volatility (annual), e.g. 0.20
- ``q``     continuous dividend yield (default 0.0)
- greeks are per-1.0 moves; ``theta`` is per-calendar-day, ``vega``/``rho`` per 1
  percentage-point (i.e. already divided by 100) — the desk-standard scaling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

OptionType = Literal["call", "put"]

_SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via erf (accurate, stdlib-only)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    if s <= 0 or k <= 0:
        raise ValueError("spot and strike must be positive")
    if t <= 0 or sigma <= 0:
        raise ValueError("time-to-expiry and sigma must be positive")
    vol_sqrt_t = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def black_scholes(
    s: float, k: float, t: float, r: float, sigma: float,
    option_type: OptionType = "call", q: float = 0.0,
) -> float:
    """Theoretical option price."""
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    disc_r = math.exp(-r * t)
    disc_q = math.exp(-q * t)
    if option_type == "call":
        return s * disc_q * _norm_cdf(d1) - k * disc_r * _norm_cdf(d2)
    return k * disc_r * _norm_cdf(-d2) - s * disc_q * _norm_cdf(-d1)


@dataclass(frozen=True, slots=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float   # per 1 vol point (0.01)
    rho: float    # per 1 rate point (0.01)


def greeks(
    s: float, k: float, t: float, r: float, sigma: float,
    option_type: OptionType = "call", q: float = 0.0,
) -> Greeks:
    """Full price + greek profile for one option."""
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    disc_r = math.exp(-r * t)
    disc_q = math.exp(-q * t)
    sqrt_t = math.sqrt(t)
    pdf_d1 = _norm_pdf(d1)

    price = black_scholes(s, k, t, r, sigma, option_type, q)
    gamma = disc_q * pdf_d1 / (s * sigma * sqrt_t)
    vega = s * disc_q * pdf_d1 * sqrt_t / 100.0

    if option_type == "call":
        delta = disc_q * _norm_cdf(d1)
        theta_yr = (
            -s * disc_q * pdf_d1 * sigma / (2.0 * sqrt_t)
            - r * k * disc_r * _norm_cdf(d2)
            + q * s * disc_q * _norm_cdf(d1)
        )
        rho = k * t * disc_r * _norm_cdf(d2) / 100.0
    else:
        delta = -disc_q * _norm_cdf(-d1)
        theta_yr = (
            -s * disc_q * pdf_d1 * sigma / (2.0 * sqrt_t)
            + r * k * disc_r * _norm_cdf(-d2)
            - q * s * disc_q * _norm_cdf(-d1)
        )
        rho = -k * t * disc_r * _norm_cdf(-d2) / 100.0

    return Greeks(
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta_yr / 365.0,
        vega=vega,
        rho=rho,
    )
