"""Rule-based market-regime classifier — the gate that keeps us out of bad setups.

Deterministic and transparent: trend from price vs. its recent mean, vol state from IV
rank. This is the #1 account-killer guard (README §1) — an LLM never overrides it; the
Phase-2 committee only reasons *within* the regime this returns.
"""

from __future__ import annotations

# Thresholds are explicit so they can be tuned and backtested.
TREND_BAND = 0.02       # ±2% of the mean counts as "range"
HIGH_VOL_RANK = 50.0    # IV rank at/above this is "high vol"


def trend_state(spot: float, price_history: list[float] | None) -> str:
    """'trend-up' / 'trend-down' / 'range' from spot vs. its recent average."""
    if not price_history:
        return "range"
    mean = sum(price_history) / len(price_history)
    if mean <= 0:
        return "range"
    if spot > mean * (1 + TREND_BAND):
        return "trend-up"
    if spot < mean * (1 - TREND_BAND):
        return "trend-down"
    return "range"


def vol_state(iv_rank: float) -> str:
    return "high-vol" if iv_rank >= HIGH_VOL_RANK else "low-vol"


def classify(iv_rank: float, spot: float, price_history: list[float] | None = None) -> str:
    """Combined regime label, e.g. 'range / high-vol' (ideal for selling condors)."""
    return f"{trend_state(spot, price_history)} / {vol_state(iv_rank)}"


def condor_friendly(regime: str) -> bool:
    """Iron condors want range-bound + rich premium; breakouts are the enemy."""
    return regime.startswith("range") and regime.endswith("high-vol")
