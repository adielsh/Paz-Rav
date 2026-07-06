"""Position — a candidate that was actually opened (paper or later, live).

This is the missing link between "here's a recommendation" and "I decided to trade it."
A Position starts open, carries the exact legs/credit it was opened at, and is later
closed by the Exit Manager (or manually) with a reason and a realized P&L.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol
from uuid import uuid4

from paz_rav.strategies.base import Candidate, Leg

CloseReason = Literal["profit_target", "stop_loss", "time_stop", "expired", "manual"]


@dataclass(frozen=True, slots=True)
class Position:
    id: str
    underlying: str
    strategy: str
    legs: tuple[Leg, ...]
    entry_credit: float
    opened_at: datetime
    langfuse_trace_id: str | None = None
    status: Literal["open", "closed"] = "open"
    close_reason: CloseReason | None = None
    closed_at: datetime | None = None
    realized_pnl: float | None = None
    meta: dict = field(default_factory=dict)

    @staticmethod
    def open_from(candidate: Candidate, opened_at: datetime,
                 langfuse_trace_id: str | None = None) -> "Position":
        # max_profit/breakevens are top-level Candidate fields, not part of its own meta —
        # copy them in explicitly so the exit rules (which read position.meta) can see them.
        meta = dict(candidate.meta)
        meta.setdefault("max_profit", candidate.max_profit)
        meta.setdefault("max_loss", candidate.max_loss)
        meta.setdefault("breakevens", list(candidate.breakevens))
        return Position(
            id=str(uuid4()), underlying=candidate.underlying, strategy=candidate.strategy,
            legs=candidate.legs, entry_credit=candidate.credit, opened_at=opened_at,
            langfuse_trace_id=langfuse_trace_id, meta=meta,
        )


class PositionRepository(Protocol):
    """Durable paper (later: live) position ledger."""

    async def save(self, position: Position) -> None: ...

    async def get(self, position_id: str) -> Position | None: ...

    async def list_open(self, underlying: str | None = None) -> list[Position]: ...

    async def list_all(self, underlying: str | None = None) -> list[Position]: ...
