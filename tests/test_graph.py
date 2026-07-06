"""LangGraph committee — the Analyst <-> Critic loop and its revision behaviour."""

import asyncio
from datetime import datetime, timezone

import pytest

from paz_rav.contracts import Feature
from paz_rav.strategies import make_strategy

pytest.importorskip("langgraph")

from paz_rav.agents import graph  # noqa: E402
from paz_rav.agents.committee import review  # noqa: E402


def feature(regime="range / high-vol", iv_rank=60.0):
    return Feature(underlying="SPX", spot=6000.0, iv_rank=iv_rank, term_slope=0.0,
                   expected_move=100.0, regime=regime, ts=datetime.now(timezone.utc))


def condor():
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=35,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.15, vrp=0.15,
    )


def test_graph_runs_and_returns_verdict():
    out = graph.run(condor(), feature())
    assert out["verdict"] in ("take", "caution", "pass")
    assert out["objection"]
    assert out["revisions"] >= 0


def test_committee_uses_langgraph_engine():
    out = asyncio.run(review(condor(), feature()))
    assert out["engine"] == "langgraph"
    assert {"verdict", "rationale", "objection", "explanation"} <= set(out)


def wide_condor():
    # wider shorts -> POP >= 0.70 so the analyst would "take" in a friendly regime
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=35,
        put_long=5600.0, put_short=5700.0, call_short=6300.0, call_long=6400.0,
        credit=20.0, sigma=0.15, vrp=0.15,
    )


def test_severe_objection_tempers_take_to_caution():
    # The analyst would "take" this high-POP condor in a friendly regime; the critic's bear
    # case (macro/gap/rally/spike) is severe -> loop back -> analyst downgrades to caution.
    from paz_rav.agents.analyst import review as analyst_review
    from paz_rav.agents.graph import _critic_node, _severe

    c = wide_condor()
    assert analyst_review(c, feature())[0] == "take"          # precondition
    st = _critic_node({"candidate": c, "feature": feature(), "verdict": "take", "revisions": 0})
    assert _severe(st["objection"]) and st["loop"] is True

    out = graph.run(c, feature())
    assert out["revisions"] >= 1
    assert out["verdict"] == "caution"
