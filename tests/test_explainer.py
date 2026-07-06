"""Explainer agent — deterministic template fallback (no API key / no network needed).

Hermetic via the autouse fixture in conftest.py, which forces an empty ANTHROPIC_API_KEY
regardless of what a real local .env file might contain.
"""

import asyncio

from paz_rav.agents import explain
from paz_rav.strategies import make_strategy


def test_iron_condor_explanation_mentions_key_numbers():
    c = make_strategy("iron_condor").build(
        underlying="SPX", spot=6000.0, dte=35,
        put_long=5700.0, put_short=5800.0, call_short=6200.0, call_long=6300.0,
        credit=20.0, sigma=0.15,
    )
    text = asyncio.run(explain(c))
    assert "SPX" in text
    assert "5800" in text and "6200" in text     # the short strikes
    assert "%" in text                            # probability of success
