"""Advisor microservice — a tiny FastAPI app that runs the close-timing debate.

Contract (the whole API surface — deliberately minimal):

    GET  /health   -> {"status": "ok", "service": "advisor"}
    POST /advise    body {"situation": {...}}  -> the debate result dict
                    (decision · confidence · rationale · analyst · critic ·
                     revisions · orchestration · engine · served_by)

The monolith computes the deterministic ``Situation`` and POSTs it here; this service runs
the Analyst -> Critic -> Decider debate (LangGraph when available, sequential otherwise,
deterministic rule-based without an API key) and returns the verdict. It holds no state and
touches no database — it's a pure inference endpoint, which is exactly why it's safe to
scale and deploy on its own.

Run it standalone:  uvicorn paz_rav.services.advisor.app:app --port 8001
The monolith reaches it by setting ADVISOR_URL=http://advisor:8001 (see config.py).
"""

from __future__ import annotations

from fastapi import FastAPI

from paz_rav import __version__
from paz_rav.agents.close_advisor import (
    Situation,
    _debate_fallback,
    _debate_llm,
)
from paz_rav.config import get_settings

app = FastAPI(title="Paz Rav — Advisor Service", version=__version__)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "advisor", "version": __version__}


@app.post("/advise")
async def advise_endpoint(payload: dict) -> dict:
    """Run the three-model debate over a pre-computed situation.

    ``payload["situation"]`` is a ``Situation`` as a plain dict (every number already
    computed by the monolith's quant core). We only weigh those numbers here.
    """
    sit = Situation(**payload["situation"])
    mem_note = payload.get("mem_note", "")   # recalled-case context computed by the caller
    settings = get_settings()

    if settings.anthropic_api_key:
        try:
            result = await _debate_llm(sit, settings, mem_note)
            result["engine"] = "llm"
        except Exception:
            result = _debate_fallback(sit)
            result["engine"] = "deterministic"
    else:
        result = _debate_fallback(sit)
        result["engine"] = "deterministic"

    result["served_by"] = "advisor-service"
    return result
