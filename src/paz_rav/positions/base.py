"""Position — a candidate that was actually opened (paper or later, live).

This is the missing link between "here's a recommendation" and "I decided to trade it."
A Position starts open. The Exit Manager never closes it by itself — the real fill
happens at your broker, not inside this system — it only sets ``alert`` to say "you
should close this now" (README's honest design: advisory, not execution). Closing is
always a deliberate user action that records the real net price you got.
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
    alert: CloseReason | None = None   # set by the Exit Manager sweep; advisory only
    close_reason: CloseReason | None = None
    closed_at: datetime | None = None
    exit_credit: float | None = None   # the REAL net price you got closing (your input)
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

    def close_manually(self, exit_credit: float, closed_at: datetime,
                       reason: CloseReason | None = None) -> "Position":
        """Record the REAL close: ``exit_credit`` is the net price you actually got
        closing the whole position (positive = you received money, negative = you paid
        money). Realized P&L is your entry credit plus that — no modeling involved.
        """
        from dataclasses import replace

        return replace(
            self, status="closed", alert=None, close_reason=reason or self.alert or "manual",
            closed_at=closed_at, exit_credit=exit_credit,
            realized_pnl=round(self.entry_credit + exit_credit, 4),
        )


class PositionRepository(Protocol):
    """Durable paper (later: live) position ledger."""

    async def save(self, position: Position) -> None: ...

    async def get(self, position_id: str) -> Position | None: ...

    async def list_open(self, underlying: str | None = None) -> list[Position]: ...

    async def list_all(self, underlying: str | None = None) -> list[Position]: ...
