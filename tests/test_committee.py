"""Committee — analyst verdict, critic objection, and the packaged review."""

import asyncio
from datetime import datetime, timezone

from paz_rav.agents import review
from paz_rav.agents.analyst import review as analyst_review
from paz_rav.agents.critic import objection
from paz_rav.contracts import Feature
from paz_rav.strategies import make_strategy


def feature(regime="range / high-vol", iv_rank=60.0):
    return Feature(underlying="SPX", spot=6000.0, iv_rank=iv_rank, term_slope=0.0,
                   expected_move=100.0, regime=regime, ts=datetime.now(timezone.utc))


def condor():
    return make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=35,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.15, vrp=0.15,
    )


def test_analyst_returns_valid_verdict():
    verdict, rationale = analyst_review(condor(), feature())
    assert verdict in ("take", "caution", "pass")
    assert isinstance(rationale, str) and rationale


def test_critic_objection_names_the_risk():
    text = objection(condor(), feature())
    assert "5800" in text and "6200" in text          # the short strikes are the risk edges
    assert "⚠️" in text


def test_committee_review_shape():
    out = asyncio.run(review(condor(), feature()))
    assert {"verdict", "rationale", "objection", "explanation"} <= set(out)
    assert out["verdict"] in ("take", "caution", "pass")
    assert "SPX" in out["explanation"]
