"""LangGraph committee — the Analyst <-> Critic loop as a stateful graph.

This is the README's Phase-2 design made real: a branching graph where the Critic can
send the decision *back* to the Analyst, who revises. The graph is the right tool exactly
because there are two agents in a loop (a single agent wouldn't need it).

Flow:
    analyst -> critic -> (if the objection is severe AND the verdict was "take":
                          loop back to analyst to reconsider, once) -> done

Everything degrades gracefully: if langgraph isn't installed, callers use the sequential
committee instead (agents/committee.py). Verdict/objection stay deterministic; Langfuse
tracing is attached when keys are present.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from paz_rav.agents.analyst import review as analyst_review
from paz_rav.agents.critic import objection as critic_objection
from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate


class CommitteeState(TypedDict, total=False):
    candidate: Candidate
    feature: Optional[Feature]
    verdict: str
    rationale: str
    objection: str
    revisions: int
    loop: bool


def _severe(objection: str) -> bool:
    """A heuristic 'the Critic pushed hard' signal — earnings/gap/spike/rally language."""
    hot = ("קפיצת", "גאפ", "ראלי", "מאקרו", "דוח")
    return sum(w in objection for w in hot) >= 2


def _analyst_node(state: CommitteeState) -> CommitteeState:
    verdict, rationale = analyst_review(state["candidate"], state.get("feature"))
    # On a revisit prompted by a severe objection, temper an over-confident "take".
    if state.get("loop") and verdict == "take":
        verdict = "caution"
        rationale = "המבקר העלה סיכון מהותי — הורדנו מ'לפתוח' ל'בזהירות'. " + rationale
    return {**state, "verdict": verdict, "rationale": rationale,
            "revisions": state.get("revisions", 0) + (1 if state.get("loop") else 0)}


def _critic_node(state: CommitteeState) -> CommitteeState:
    obj = critic_objection(state["candidate"], state.get("feature"))
    loop = (state["verdict"] == "take" and _severe(obj) and state.get("revisions", 0) == 0)
    return {**state, "objection": obj, "loop": loop}


def _route(state: CommitteeState) -> str:
    return "analyst" if state.get("loop") else "done"


def _build_graph():
    from langgraph.graph import END, StateGraph

    g = StateGraph(CommitteeState)
    g.add_node("analyst", _analyst_node)
    g.add_node("critic", _critic_node)
    g.set_entry_point("analyst")
    g.add_edge("analyst", "critic")
    g.add_conditional_edges("critic", _route, {"analyst": "analyst", "done": END})
    return g.compile()


_graph = None


def available() -> bool:
    try:
        import langgraph  # noqa: F401
        return True
    except Exception:
        return False


def run(candidate: Candidate, feature: Feature | None) -> dict:
    """Run the committee graph; returns verdict/rationale/objection (+ revisions)."""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    _maybe_trace(candidate)
    out = _graph.invoke({"candidate": candidate, "feature": feature, "revisions": 0})
    return {
        "verdict": out["verdict"],
        "rationale": out["rationale"],
        "objection": out["objection"],
        "revisions": out.get("revisions", 0),
    }


def _maybe_trace(candidate: Candidate) -> None:
    """Best-effort Langfuse event; silently skipped when unconfigured."""
    from paz_rav.config import get_settings

    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return
    try:
        from langfuse import Langfuse

        Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key,
                 host=s.langfuse_host).create_event(
            name="committee_review",
            metadata={"underlying": candidate.underlying, "strategy": candidate.strategy,
                      "score": candidate.score},
        )
    except Exception:
        pass
