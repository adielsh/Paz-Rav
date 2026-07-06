"""Exit manager — watches open positions and flags the ones you should close.

Honest design: this never closes a position by itself. The real fill happens at your
broker, not inside this system, so the sweep only sets ``alert`` — a clear "close this
now" signal shown on the dashboard. You confirm the actual close (and the real price you
got) via ``close_position``, which is what closes the learning loop: the realized P&L
scores back onto the exact Langfuse trace the opening decision produced.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from paz_rav.positions.base import Position, PositionRepository
from paz_rav.positions.exit_rules import ExitConfig, check_exit


async def sweep(
    repo: PositionRepository, underlying: str, spot: float, today: date,
    cfg: ExitConfig | None = None,
) -> list[Position]:
    """Re-check every open position for ``underlying``; update its ``alert``.

    Returns the positions whose alert just turned on this sweep (newly flagged), so
    callers can notify. A position whose trigger condition is no longer true (e.g. price
    moved back) has its alert cleared automatically.
    """
    cfg = cfg or ExitConfig()
    newly_flagged: list[Position] = []
    for pos in await repo.list_open(underlying):
        should_close, reason = check_exit(pos, spot, today, cfg)
        new_alert = reason if should_close else None
        if new_alert != pos.alert:
            updated = replace(pos, alert=new_alert)
            await repo.save(updated)
            if new_alert is not None:
                newly_flagged.append(updated)
    return newly_flagged


async def close_position(
    repo: PositionRepository, position_id: str, exit_credit: float,
    closed_at: datetime, reason: str | None = None,
) -> Position | None:
    """Record the real close the user confirms, and score the outcome back to Langfuse."""
    pos = await repo.get(position_id)
    if pos is None or pos.status != "open":
        return None
    closed = pos.close_manually(exit_credit, closed_at, reason=reason)  # type: ignore[arg-type]
    await repo.save(closed)
    _maybe_score(closed)
    return closed


def _maybe_score(position: Position) -> None:
    """Best-effort: score the realized P&L back onto the original Langfuse trace.

    Silently skipped when Langfuse isn't configured, the trace wasn't captured (e.g. the
    sequential committee fallback), or the call fails for any other reason — this must
    never block closing a position.
    """
    if not position.langfuse_trace_id:
        return
    from paz_rav.config import get_settings

    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return
    try:
        from langfuse import Langfuse

        Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key,
                host=s.langfuse_host).create_score(
            trace_id=position.langfuse_trace_id, name="realized_pnl",
            value=position.realized_pnl or 0.0, data_type="NUMERIC",
            comment=f"{position.underlying} {position.strategy} closed: {position.close_reason}",
        )
    except Exception:
        pass
