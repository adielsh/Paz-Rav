"""Positions — the missing link between "here's a recommendation" and "I opened it."

A Position is a Candidate that was actually opened (paper today, live later). The Exit
Manager watches open positions and flags the ones you should close (advisory — never
auto-closes, since the real fill happens at your broker); you confirm the close with the
real price you got (README Phase 3).
"""

from paz_rav.positions.base import CloseReason, Position, PositionRepository
from paz_rav.positions.exit_manager import close_position, sweep
from paz_rav.positions.exit_rules import ExitConfig, check_exit, mark_to_market
from paz_rav.positions.memory import InMemoryPositionRepository

__all__ = [
    "Position",
    "PositionRepository",
    "CloseReason",
    "InMemoryPositionRepository",
    "ExitConfig",
    "check_exit",
    "mark_to_market",
    "sweep",
    "close_position",
]
