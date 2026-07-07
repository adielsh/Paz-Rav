"""Agents — the judgment/explanation layer (Phase 2).

Agents reason over pre-computed structured data; they never compute the numbers. The
first agent is the Explainer (plain-language summaries). The Analyst + Critic committee
lands here next.
"""

from paz_rav.agents.close_advisor import advise
from paz_rav.agents.committee import review
from paz_rav.agents.explainer import explain

__all__ = ["advise", "explain", "review"]
