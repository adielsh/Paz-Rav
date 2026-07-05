"""Backtester — replay history through the SAME analytics + builder code (one path).

Proves the edge before capital is risked: win rate, avg P&L, max drawdown per strategy.
"""

from paz_rav.backtest.payoff import pnl_at_expiry
from paz_rav.backtest.runner import BacktestResult, run

__all__ = ["pnl_at_expiry", "BacktestResult", "run"]
