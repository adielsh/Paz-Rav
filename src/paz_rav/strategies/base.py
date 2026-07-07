"""Shared types + the Strategy interface every structure obeys."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol, runtime_checkable

Side = Literal["buy", "sell"]
OptionType = Literal["call", "put"]


@dataclass(frozen=True, slots=True)
class Leg:
    """One option leg of a structure. Premium/greeks are per share.

    ``expiry`` and ``iv`` are set for multi-expiry structures (diagonals): a leg whose
    expiry is later than the evaluation date is still alive and must be *priced*, not
    just taken at intrinsic. ``expiry=None`` means the leg expires at the structure's
    evaluation date (the single-expiry case, e.g. an iron condor).

    ``delta`` is the leg's delta at scan time (signed: puts negative) — carried so the
    dashboard can show each leg's delta; None when built without chain data (tests,
    hand-built structures).
    """

    side: Side
    option_type: OptionType
    strike: float
    quantity: int = 1
    expiry: date | None = None
    iv: float | None = None
    delta: float | None = None


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
    ``enumerate``. Carries its ``expiry``/``dte`` so multi-expiry structures (diagonals)
    can pick short legs from one expiry and long legs from another.
    """

    right: OptionType
    strike: float
    mid: float
    delta: float
    iv: float
    open_interest: int
    rel_spread: float  # (ask - bid) / mid — tighter is more liquid
    expiry: date
    dte: int


@dataclass(frozen=True, slots=True)
class MarketContext:
    """The current regime/vol backdrop — lets a strategy judge if *now* is its time.

    Iron condor wants range-bound + high IV (sell rich premium); diagonals are long vega
    and prefer low IV (buy vol cheap). Each strategy turns this into a ``regime_fit``
    multiplier on its score, so the global ranking surfaces the right strategy for now.
    """

    regime: str = "range / low-vol"
    iv_rank: float = 50.0
    term_slope: float = 0.0
    rsi: float | None = None
    earnings_soon: bool = False   # True if an earnings report is within ~2 weeks (skip DACS)


@dataclass(frozen=True, slots=True)
class BuildConfig:
    """Knobs for candidate enumeration. Explicit so they can be tuned and backtested."""

    target_dte: int = 35                        # iron-condor front DTE (1-2 wks .. 45d)
    short_deltas: tuple[float, ...] = (16.0,)   # short-strike deltas to try (0..50)
    wing_strikes: tuple[int, ...] = (1, 2)      # iron-condor wings: N strikes out (adapts to any product)
    wing_widths: tuple[float, ...] = (5.0,)     # dollar wings (diagonals only)
    min_open_interest: int = 0
    max_rel_spread: float = 0.60                # reject legs wider than this
    r: float = 0.04
    top_n: int = 10
    vrp: float = 0.0                            # volatility risk premium (realized = iv*(1-vrp))
    # ---- DACS knobs ----
    dacs_short_dte: int = 35                     # sell ~1 month out
    dacs_gap_days: int = 30                      # buy ~1 month beyond the short
    dacs_otm: float = 0.10                       # short call ~10% OTM
    dacs_max_delta: float = 0.20                 # short delta cap
    dacs_min_long_price: float = 1.0             # long option must be worth > $1
    dacs_min_fast_ratio: float = 0.12            # long value / risk; below this = skip


@runtime_checkable
class OptionStrategy(Protocol):
    """The one contract every strategy implements (Strategy pattern).

    ``enumerate`` turns an annotated chain into ranked candidates. Enumeration is
    strategy-specific; the candidate shape and the expectancy-based score are shared, so
    the builder treats every strategy uniformly and ranks them against each other.
    """

    name: str

    def enumerate(
        self, *, underlying: str, spot: float, chain: list[AnnotatedQuote],
        config: BuildConfig, today: date, ctx: MarketContext,
    ) -> list[Candidate]:
        """Enumerate and score candidate structures from an annotated (multi-expiry) chain."""
        ...
