"""Walk-forward backtest — evaluate closed trades and report the metrics that matter.

Feed it (candidate, terminal_price) pairs in chronological order; it returns win rate,
average P&L, total, and max drawdown of the equity curve — the numbers you decide to
trust the strategy on (README §11.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from paz_rav.backtest.payoff import pnl_at_expiry
from paz_rav.strategies.base import Candidate


@dataclass(frozen=True, slots=True)
class BacktestResult:
    trades: int
    wins: int
    win_rate: float
    avg_pnl: float
    total_pnl: float
    max_drawdown: float
    equity_curve: list[float] = field(default_factory=list)


def run(trades: list[tuple[Candidate, float]]) -> BacktestResult:
    """Evaluate a chronological list of (candidate, terminal_price) trades."""
    if not trades:
        return BacktestResult(0, 0, 0.0, 0.0, 0.0, 0.0, [])

    pnls = [pnl_at_expiry(c, price) for c, price in trades]
    wins = sum(1 for p in pnls if p > 0)

    equity: list[float] = []
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        running += p
        equity.append(round(running, 4))
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    n = len(pnls)
    return BacktestResult(
        trades=n,
        wins=wins,
        win_rate=round(wins / n, 4),
        avg_pnl=round(sum(pnls) / n, 4),
        total_pnl=round(sum(pnls), 4),
        max_drawdown=round(max_dd, 4),
        equity_curve=equity,
    )
