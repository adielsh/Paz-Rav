"""Read-only proxy to the Paz Rav strategy engine (src/paz_rav/, container `engine`).

The engine is the multi-underlying half of this system: it scans a universe of names,
ranks Iron Condor and DACS candidates with a deterministic quant core, and runs them past
an AI judgment layer. It is **advisory only** — it holds no broker connection and exposes
no route that could place, modify or cancel an order. Proxying it therefore does not
weaken the standing invariant that this API cannot trade.

Why a proxy at all, rather than another nginx location block: the engine runs with its own
Firebase auth gate switched off (it would otherwise be a second, unrelated login), and it
is not published on the docker network's edge. This router is its only door, and every
route here depends on USER_ID — so engine data is behind exactly the same session cookie
as /positions and /trades.

Only GETs are forwarded, and only the six read routes named below; the engine's own
POST routes (open a paper position, close one, force an AI debate) are deliberately not
reachable from the console.

Like ib_bridge, this degrades instead of failing: if the engine is down or slow, every
route answers {"available": false, "error": ...} with HTTP 200 so the console renders an
offline panel rather than an error page. A stopped engine must never break the console.
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Depends

log = logging.getLogger("engine_proxy")

ENGINE_URL = os.getenv("ENGINE_URL", "http://engine:8000")
# The engine's scan is in-memory and answers fast; the ceiling here is really about not
# letting a wedged engine hold a console request open. 15s is well past its p99.
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    """One client for the process — a new AsyncClient per request leaks connections."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=ENGINE_URL, timeout=_TIMEOUT)
    return _client


async def shutdown() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _get(path: str, **params) -> dict:
    """Forward one GET. Never raises — an unreachable engine is a normal state here."""
    try:
        r = await _http().get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        payload = r.json()
    except httpx.HTTPStatusError as e:
        log.warning("engine %s -> HTTP %s", path, e.response.status_code)
        return {"available": False, "error": f"engine returned HTTP {e.response.status_code}"}
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return {"available": False, "error": "engine is not running"}
    except httpx.TimeoutException:
        return {"available": False, "error": "engine timed out"}
    except Exception as e:                      # malformed JSON, transport oddities
        log.warning("engine %s -> %s", path, e)
        return {"available": False, "error": str(e)}
    # The engine has no idea it is being proxied, so it never sets this. Stamping it here
    # means the frontend has one field to branch on for every engine route.
    if isinstance(payload, dict):
        payload.setdefault("available", True)
        return payload
    return {"available": True, "data": payload}


def build_router(user_id) -> APIRouter:
    """`user_id` is auth.make_dependencies()' session dependency — the whole point."""
    router = APIRouter(prefix="/engine", tags=["engine"], dependencies=[Depends(user_id)])

    @router.get("/health")
    async def engine_health() -> dict:
        """Engine liveness + which market-data feed it is actually running on.

        `data_source` is what lets the console label the page honestly instead of
        hard-coding "delayed" — the engine reads yfinance today, not the IB gateway.
        """
        return await _get("/health")

    @router.get("/top")
    async def engine_top(n: int = 10) -> dict:
        """The best `n` candidates per strategy, across every underlying the engine scans.

        Already filtered and ranked by the engine: committee "pass" verdicts are dropped,
        "take" outranks "caution", and no single underlying contributes more than two rows.
        """
        return await _get("/api/top", n=n)

    @router.get("/state")
    async def engine_state() -> dict:
        """Latest computed features + candidates for every underlying, in one call."""
        return await _get("/api/state")

    @router.get("/candidates/{underlying}")
    async def engine_candidates(underlying: str) -> dict:
        return await _get(f"/api/candidates/{underlying}")

    @router.get("/payoff/{underlying}/{idx}")
    async def engine_payoff(underlying: str, idx: int) -> dict:
        """61-point payoff grid for one candidate, priced by the engine's digital twin."""
        return await _get(f"/api/payoff/{underlying}/{idx}")

    @router.get("/explain/{underlying}/{idx}")
    async def engine_explain(underlying: str, idx: int) -> dict:
        """Plain-language explanation of a candidate. Deterministic template, not an LLM."""
        return await _get(f"/api/explain/{underlying}/{idx}")

    return router
