"""Quant core — deterministic, pure functions. No AI, no side effects.

These reference implementations use only the Python standard library so the whole
test suite runs with zero extra installs. The optional `quant` extra (numpy / scipy /
py_vollib) is for performance and cross-validation, not correctness — the parity test
(docs/ROADMAP.md) checks these against py_vollib when it is installed.
"""

from paz_rav.quant.greeks import Greeks, black_scholes, greeks
from paz_rav.quant.implied_vol import implied_vol
from paz_rav.quant.pop import expected_move, prob_between, prob_of_profit

__all__ = [
    "Greeks",
    "black_scholes",
    "greeks",
    "implied_vol",
    "expected_move",
    "prob_between",
    "prob_of_profit",
]
