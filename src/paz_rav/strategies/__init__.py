"""Option strategies — the Strategy pattern behind a Factory registry.

Every structure implements the same :class:`OptionStrategy` interface, so the builder
and backtester treat them uniformly and a 4th strategy is a new file, not a rewrite.
"""

from paz_rav.strategies.base import (
    AnnotatedQuote,
    BuildConfig,
    Candidate,
    Leg,
    MarketContext,
    OptionStrategy,
)
from paz_rav.strategies.dacs import DACS
from paz_rav.strategies.diagonal import Diagonal
from paz_rav.strategies.double_diagonal import DoubleDiagonal
from paz_rav.strategies.iron_condor import IronCondor
from paz_rav.strategies.registry import (
    FOCUS_STRATEGIES,
    list_strategies,
    make_strategy,
    register,
)

__all__ = [
    "AnnotatedQuote",
    "BuildConfig",
    "Candidate",
    "Leg",
    "MarketContext",
    "OptionStrategy",
    "IronCondor",
    "DACS",
    "DoubleDiagonal",
    "Diagonal",
    "FOCUS_STRATEGIES",
    "make_strategy",
    "list_strategies",
    "register",
]
