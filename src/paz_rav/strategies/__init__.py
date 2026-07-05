"""Option strategies — the Strategy pattern behind a Factory registry.

Every structure implements the same :class:`OptionStrategy` interface, so the builder
and backtester treat them uniformly and a 4th strategy is a new file, not a rewrite.
"""

from paz_rav.strategies.base import (
    AnnotatedQuote,
    BuildConfig,
    Candidate,
    Leg,
    OptionStrategy,
)
from paz_rav.strategies.iron_condor import IronCondor
from paz_rav.strategies.registry import list_strategies, make_strategy, register

__all__ = [
    "AnnotatedQuote",
    "BuildConfig",
    "Candidate",
    "Leg",
    "OptionStrategy",
    "IronCondor",
    "make_strategy",
    "list_strategies",
    "register",
]
