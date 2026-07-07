"""Close-Timing Advisor — the deterministic-fallback path (no API key, no network).

With ANTHROPIC_API_KEY empty (conftest guarantees it), advise() must still return the
full debate shape via the rule-based fallback, and every NUMBER in the situation must be
the one the quant core computed — never invented. Also verifies the state-signature cache
(ordinary refreshes hit it; force=True busts it), matching the production cost story.
"""

import asyncio
from datetime import date, datetime, timezone

from paz_rav.agents.close_advisor import advise, build_situation
from paz_rav.contracts import Feature
from paz_rav.positions import Position
from paz_rav.positions.exit_rules import mark_to_market
from paz_rav.strategies import make_strategy

TODAY = date(2026, 1, 15)


def _condor(dte=35):
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=dte,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.15, today=TODAY,
    )


def _position(dte=35):
    return Position.open_from(_condor(dte), datetime(2026, 1, 15, tzinfo=timezone.utc))


def _feature(spot=6000.0):
    return Feature(underlying="SPX", spot=spot, iv_rank=30.0, term_slope=0.0,
                   expected_move=100.0, regime="range / high-vol", rsi=55.0,
                   ts=datetime(2026, 1, 15, tzinfo=timezone.utc))


# ---- The deterministic situation carries only computed numbers ----

def test_situation_numbers_match_the_quant_core():
    pos = _position()
    sit = build_situation(pos, spot=6000.0, today=TODAY, feature=_feature())
    # unrealized P&L is exactly the digital-twin mark-to-market, not a guess
    assert sit.unrealized_pnl == round(mark_to_market(pos, 6000.0, TODAY), 4)
    assert sit.dte == 35
    assert sit.short_strikes == [5800.0, 6200.0]
    # min cushion to either tested side, spot centred between the shorts
    assert sit.distance_to_stop == 200.0
    assert sit.exit_rule_flag is None          # nothing triggers mid-trade
    assert sit.iv_rank == 30.0 and sit.regime == "range / high-vol"


def test_situation_flags_breach_like_the_exit_rule():
    pos = _position()
    sit = build_situation(pos, spot=6250.0, today=TODAY, feature=_feature(6250.0))
    assert sit.exit_rule_flag == "stop_loss"   # past the short call, same as check_exit
    assert sit.distance_to_stop < 0            # cushion is negative once breached


# ---- advise() returns the full debate shape via the offline fallback ----

def test_advise_fallback_shape_and_engine():
    pos = _position()
    out = asyncio.run(advise(pos, spot=6000.0, today=TODAY, feature=_feature()))
    assert out["engine"] == "deterministic"    # no API key in tests
    assert out["decision"] in ("hold", "close", "reduce")
    assert set(("analyst", "critic")).issubset(out)
    assert out["analyst"]["reasons"] and out["critic"]["reasons"]
    # the critic argues the opposite corner of the analyst
    assert out["analyst"]["stance"] != out["critic"]["stance"]
    assert out["situation"]["underlying"] == "SPX"
    assert "computed_at" in out


def test_advise_biases_to_close_on_breach():
    pos = _position()
    out = asyncio.run(advise(pos, spot=6300.0, today=TODAY, feature=_feature(6300.0),
                             force=True))
    assert out["decision"] == "close"          # exit rule active -> close bias


# ---- State-signature cache: refreshes hit it, force busts it ----

def test_cache_hits_then_force_recomputes():
    pos = _position()
    a1 = asyncio.run(advise(pos, spot=6000.0, today=TODAY, feature=_feature()))
    a2 = asyncio.run(advise(pos, spot=6000.0, today=TODAY, feature=_feature()))
    assert a1 is a2                             # same market state -> served from cache
    a3 = asyncio.run(advise(pos, spot=6000.0, today=TODAY, feature=_feature(), force=True))
    assert a3 is not a1                         # "check now" bypasses the cache


# ---- LangGraph orchestration wiring (no network — graph compiles with the right shape) ----

def test_debate_graph_compiles_with_analyst_critic_decider_and_loop():
    import pytest
    pytest.importorskip("langgraph")   # skip cleanly where the AI extra isn't installed
    from paz_rav.agents import close_advisor as ca

    graph = ca._build_debate_graph()
    nodes = set(graph.get_graph().nodes)
    assert {"analyst", "critic", "decider"}.issubset(nodes)
    # the conditional edge back to the analyst is what makes this a loop, not a line
    assert ca._g_route({"loop": True}) == "analyst"
    assert ca._g_route({"loop": False}) == "done"


# ---- The extracted advisor microservice ----

def test_advisor_service_advise_endpoint_returns_debate():
    from dataclasses import asdict

    from fastapi.testclient import TestClient

    from paz_rav.agents.close_advisor import build_situation
    from paz_rav.services.advisor.app import app

    sit = build_situation(_position(), spot=6000.0, today=TODAY, feature=_feature())
    with TestClient(app) as client:
        r = client.post("/advise", json={"situation": asdict(sit)})
        assert r.status_code == 200
        d = r.json()
        assert d["decision"] in ("hold", "close", "reduce")
        assert d["served_by"] == "advisor-service"
        assert d["engine"] == "deterministic"        # no API key in tests
        assert d["analyst"]["reasons"] and d["critic"]["reasons"]


def test_resolve_debate_prefers_remote_and_circuit_breaks(monkeypatch):
    """advisor_url set -> use the service; if it errors, fall back in-process (never down)."""
    import types

    from paz_rav.agents import close_advisor as ca

    sit = ca.build_situation(_position(), spot=6000.0, today=TODAY, feature=_feature())
    fake = types.SimpleNamespace(advisor_url="http://advisor:8001",
                                 anthropic_api_key="", advisor_timeout=5.0)

    async def ok_remote(_sit, _settings):
        return {"decision": "hold", "confidence": 0.9, "rationale": "from service",
                "analyst": {"stance": "hold", "reasons": ["x"]},
                "critic": {"stance": "close", "reasons": ["y"]}, "engine": "llm"}

    monkeypatch.setattr(ca, "_debate_remote", ok_remote)
    out = asyncio.run(ca._resolve_debate(sit, fake))
    assert out["served_by"] == "advisor-service" and out["decision"] == "hold"

    async def boom_remote(_sit, _settings):
        raise RuntimeError("advisor down")

    monkeypatch.setattr(ca, "_debate_remote", boom_remote)
    out2 = asyncio.run(ca._resolve_debate(sit, fake))   # circuit breaker kicks in
    assert out2["engine"] == "deterministic"            # ran in-process instead
    assert "served_by" not in out2
