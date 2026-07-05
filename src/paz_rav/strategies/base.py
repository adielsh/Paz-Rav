"""Shared types + the Strategy interface every structure obeys."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Side = Literal["buy", "sell"]
OptionType = Literal["call", "put"]


@dataclass(frozen=True, slots=True)
class Leg:
    """One option leg of a structure. Premium/greeks are per share."""

    side: Side
    option_type: OptionType
    strike: float
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class Candidate:
    """A concrete, priced trade idea produced by a strategy.

    All dollar figures are per share (multiply by contract multiplier * lots for
    account P&L). ``score`` is filled by the strategy's :meth:`OptionStrategy.score`.
    """

    underlying: str
    strategy: str
    dte: int
    legs: tuple[Leg, ...]
    credit: float          # net premium received (positive for a credit structure)
    width: float           # wing width of the defined-risk spread
    max_profit: float
    max_loss: float
    breakevens: tuple[float, ...]
    pop: float = 0.0       # probability of profit in [0, 1]
    score: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnnotatedQuote:
    """A chain quote enriched with the numbers enumeration needs: delta, IV, liquidity.

    Produced by the builder (which computes greeks); consumed by each strategy's
    ``enumerate``. Keeping it plain (no pydantic) keeps enumeration fast and testable.
    """

    right: OptionType
    strike: float
    mid: float
    delta: float
    iv: float
    open_interest: int
    rel_spread: float  # (ask - bid) / mid — tighter is more liquid


@dataclass(frozen=True, slots=True)
class BuildConfig:
    """Knobs for candidate enumeration. Explicit so they can be tuned and backtested."""

    target_dte: int = 45
    short_deltas: tuple[float, ...] = (16.0,)   # short-strike deltas to try (0..50)
    wing_widths: tuple[float, ...] = (5.0,)     # spread widths to try
    min_open_interest: int = 0
    max_rel_spread: float = 0.60                # reject legs wider than this
    r: float = 0.04
    top_n: int = 10


@runtime_checkable
class OptionStrategy(Protocol):
    """The one contract every strategy implements (Strategy pattern).

    ``enumerate`` turns an annotated chain into ranked candidates; ``build`` prices one
    explicit structure; ``score`` ranks. Enumeration is strategy-specific; scoring and
    the candidate shape are shared, so the builder treats all strategies uniformly.
    """

    name: str

    def enumerate(
        self, *, underlying: str, spot: float, dte: int,
        chain: list[AnnotatedQuote], config: BuildConfig,
    ) -> list[Candidate]:
        """Enumerate and score candidate structures from an annotated chain."""
        ...

    def score(self, c: Candidate) -> float:
        """Return a comparable ranking score for a candidate (higher = better)."""
        ...
