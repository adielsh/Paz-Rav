"""Committee — runs the Analyst then the Critic over one position and packages the result.

Separation of concerns + adversarial review: the Analyst proposes a verdict, the Critic
argues against it, and the Explainer writes the plain-language summary. Today it's a simple
sequential call (README's honest note: start as two calls, wrap in LangGraph when you want
the loop). The verdict/objection are deterministic; the summary uses Claude when keyed.
"""

from __future__ import annotations

from paz_rav.agents.analyst import review as analyst_review
from paz_rav.agents.critic import objection as critic_objection
from paz_rav.agents.explainer import explain
from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate


async def review(c: Candidate, feature: Feature | None) -> dict:
    """Run the committee. Uses the LangGraph Analyst<->Critic loop when available, else
    a plain sequential pass. Either way the shape is identical to callers."""
    from paz_rav.agents import graph

    if graph.available():
        try:
            g = graph.run(c, feature)
            return {**g, "explanation": await explain(c), "engine": "langgraph"}
        except Exception:
            pass

    verdict, rationale = analyst_review(c, feature)
    return {
        "verdict": verdict,                       # take | caution | pass
        "rationale": rationale,                   # analyst's reasoning
        "objection": critic_objection(c, feature),  # critic's bear case
        "explanation": await explain(c),          # plain-language summary
        "engine": "sequential",
    }
