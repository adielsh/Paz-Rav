"""Exit rules — deterministic, per-strategy, matching the documented management rules.

Never guesses: every check compares against numbers already computed by the quant
valuation engine or stored on the position at open time. No AI here — same principle as
the rest of the deterministic core (README §2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from paz_rav.positions.base import CloseReason, Position
from paz_rav.quant.valuation import structure_pnl


@dataclass(frozen=True, slots=True)
class ExitConfig:
    """Tunable thresholds. Defaults match the documented rules (README §5, DACS guide)."""

    # Iron condor: take profit early, time-stop near expiry, or cut a tested side.
    condor_profit_target: float = 0.50     # close at 50% of max credit captured
    condor_time_stop_dte: int = 21          # close at 21 DTE regardless
    # DACS: cut at short_strike + offset (offset negative -> a level BELOW the strike);
    # -1.0 = aggressive, -5.0 = conservative (your own rule, DacsGuide "נקודת סטופ").
    dacs_stop_offset: float = -5.0
    dacs_profit_multiple: float = 3.0       # close near ~3x the entry debit
    dacs_time_stop_days_before_expiry: int = 14   # close ~2 weeks before the short's expiry
    r: float = 0.04


def _front_expiry(position: Position) -> date:
    """The nearer of the position's leg expiries (the short's, for multi-expiry DACS)."""
    return min(leg.expiry for leg in position.legs if leg.expiry)


def mark_to_market(position: Position, spot: float, today: date, r: float = 0.04) -> float:
    """Current unrealized P&L if the position were closed today.

    Reuses the same digital-twin valuation the builder scores candidates with — legs not
    yet expired are priced at their remaining time value, not assumed worthless.
    """
    sigma = float(position.meta.get("sigma", 0.20))
    return structure_pnl(position.entry_credit, position.legs, spot, today, r, sigma)


def check_condor(position: Position, spot: float, today: date,
                 cfg: ExitConfig) -> tuple[bool, CloseReason | None]:
    dte = (_front_expiry(position) - today).days
    if dte <= cfg.condor_time_stop_dte:
        return True, "time_stop"

    shorts = sorted(leg.strike for leg in position.legs if leg.side == "sell")
    if shorts and (spot <= shorts[0] or spot >= shorts[-1]):
        return True, "stop_loss"   # a short strike has been breached

    max_profit = float(position.meta.get("max_profit", position.entry_credit))
    if max_profit > 0:
        unrealized = mark_to_market(position, spot, today, cfg.r)
        if unrealized >= cfg.condor_profit_target * max_profit:
            return True, "profit_target"
    return False, None


def check_dacs(position: Position, spot: float, today: date,
               cfg: ExitConfig) -> tuple[bool, CloseReason | None]:
    dte = (_front_expiry(position) - today).days
    if dte <= cfg.dacs_time_stop_days_before_expiry:
        return True, "time_stop"

    short = next(leg for leg in position.legs if leg.side == "sell")
    stop_level = short.strike + cfg.dacs_stop_offset   # offset is negative -> below strike
    if spot >= stop_level:
        return True, "stop_loss"

    entry_debit = max(-position.entry_credit, 0.0)
    if entry_debit > 0:
        unrealized = mark_to_market(position, spot, today, cfg.r)
        if unrealized >= cfg.dacs_profit_multiple * entry_debit:
            return True, "profit_target"
    return False, None


def check_exit(position: Position, spot: float, today: date,
              cfg: ExitConfig | None = None) -> tuple[bool, CloseReason | None]:
    """Dispatch to the strategy-specific rule set."""
    cfg = cfg or ExitConfig()
    if position.strategy == "iron_condor":
        return check_condor(position, spot, today, cfg)
    if position.strategy == "dacs":
        return check_dacs(position, spot, today, cfg)
    return False, None
