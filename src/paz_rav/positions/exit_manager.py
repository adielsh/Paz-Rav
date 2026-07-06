"""Exit manager — watches open positions and closes them per the deterministic rules.

This is the piece that closes the learning loop (README §6, §10 Phase 3): when a
position closes, its realized P&L is scored back onto the exact Langfuse trace the
original committee decision produced — so you can later ask which regimes/verdicts
actually made money.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

from paz_rav.positions.base import Position, PositionRepository
from paz_rav.positions.exit_rules import ExitConfig, check_exit, mark_to_market


async def sweep(
    repo: PositionRepository, underlying: str, spot: float, today: date,
    cfg: ExitConfig | None = None,
) -> list[Position]:
    """Check every open position for ``underlying``; close any that trigger an exit rule.

    Returns the positions closed this sweep (empty if none triggered).
    """
    cfg = cfg or ExitConfig()
    closed: list[Position] = []
    for pos in await repo.list_open(underlying):
        should_close, reason = check_exit(pos, spot, today, cfg)
        if not should_close:
            continue
        realized = mark_to_market(pos, spot, today, cfg.r)
        closed_pos = replace(
            pos, status="closed", close_reason=reason,
            closed_at=datetime.now(timezone.utc), realized_pnl=round(realized, 4),
        )
        await repo.save(closed_pos)
        _maybe_score(closed_pos)
        closed.append(closed_pos)
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
