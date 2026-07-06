"""RSI — Wilder's Relative Strength Index from a close series.

DACS wants a stable name around RSI ~60, so the feature engine computes it from recent
closes and the strategy gates on it. Pure stdlib.
"""

from __future__ import annotations


def rsi(prices: list[float], period: int = 14) -> float | None:
    """Classic RSI over ``period`` (simple average of gains/losses). None if too short."""
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    gains = sum(d for d in recent if d > 0) / period
    losses = sum(-d for d in recent if d < 0) / period
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100.0 - 100.0 / (1.0 + rs), 2)
