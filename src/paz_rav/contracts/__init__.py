"""Shared data contracts — the Pydantic schemas every module agrees on.

These are the messages that flow across module (and later, service) boundaries:
raw quotes in, computed features and candidates out. Keeping them in one place is
what lets modules talk without reaching into each other's internals.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

OptionRight = Literal["call", "put"]


class UnderlyingQuote(BaseModel):
    symbol: str
    price: float
    ts: datetime


class OptionQuote(BaseModel):
    """A single option contract's live quote (normalized from the vendor)."""

    underlying: str
    right: OptionRight
    strike: float
    expiry: date
    bid: float
    ask: float
    last: float | None = None
    open_interest: int | None = None
    implied_vol: float | None = None
    ts: datetime

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


class Feature(BaseModel):
    """Computed, per-underlying features — the analytics module's output.

    Everything downstream reasons over these, never over raw ticks.
    """

    underlying: str
    spot: float
    iv_rank: float = Field(ge=0, le=100)
    term_slope: float
    expected_move: float
    regime: str  # e.g. "range-low-vol", "trend-expanding"
    ts: datetime
