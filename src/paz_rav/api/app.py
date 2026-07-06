"""FastAPI app — REST reads + a WebSocket that fans out the bus to the dashboard.

The app factory wires the deterministic engine (feed -> pipeline -> stores + bus) and
runs a background scan loop. The browser talks only to this module (README §4A).

Run locally (real data):   uvicorn paz_rav.api.app:app --reload
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from paz_rav import __version__
from paz_rav.backtest import pnl_at_expiry
from paz_rav.bus import CH_CANDIDATES, CH_FEATURES, InMemoryBus
from paz_rav.quant.valuation import structure_pnl
from paz_rav.config import get_settings
from paz_rav.pipeline import Pipeline
from paz_rav.scheduler import Scheduler
from paz_rav.store.memory import (
    InMemoryCandidateRepository,
    InMemoryFeatureStore,
    InMemoryIVHistory,
)
from paz_rav.store.serialize import candidate_to_dict
from paz_rav.strategies import FOCUS_STRATEGIES, BuildConfig, list_strategies

log = logging.getLogger("paz_rav.api")
_WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


async def _build_real_stores(settings):
    """Real Redis + Postgres stores. MUST run on the same event loop that will serve
    requests — asyncpg's pool is bound to whatever loop creates it, so building it via a
    throwaway ``asyncio.run()`` before uvicorn starts its own loop causes every later
    query to hang (the pool belongs to a loop that's already closed). Calling this from
    inside the FastAPI lifespan guarantees it's built on uvicorn's real loop.
    """
    import redis.asyncio as aioredis

    from paz_rav.bus.redis_bus import RedisBus
    from paz_rav.store.postgres_store import PostgresCandidateRepository
    from paz_rav.store.redis_store import RedisFeatureStore, RedisIVHistory

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    candidate_repo = await PostgresCandidateRepository.connect(settings.database_url)
    return RedisFeatureStore(r), RedisIVHistory(r), RedisBus(r), candidate_repo


def create_app(
    *, feed=None, underlyings: list[str] | None = None,
    interval: float = 60.0, initial_scan: bool = True,
    config: BuildConfig | None = None, today: date | None = None,
) -> FastAPI:
    settings = get_settings()
    if feed is None:
        if settings.paz_data == "fixture":
            from paz_rav.adapters.market_data import ReplayMarketData
            fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sample_market.json"
            feed = ReplayMarketData(fixture)
            underlyings = underlyings or ["SPX", "SPY", "QQQ", "IWM", "NVDA", "MSFT", "GOOGL", "AMZN", "CSCO"]
            today = today if today is not None else date(2026, 1, 15)  # fixture as-of
        else:
            from paz_rav.adapters import YFinanceMarketData
            feed = YFinanceMarketData()
    underlyings = underlyings or settings.underlying_list
    config = config or BuildConfig(
        target_dte=settings.condor_target_dte,
        short_deltas=(16.0, 25.0), wing_widths=(5.0, 10.0),
        min_open_interest=10, max_rel_spread=0.6, top_n=6, vrp=settings.vrp,
        dacs_short_dte=settings.dacs_short_dte, dacs_gap_days=settings.dacs_gap_days,
        dacs_otm=settings.dacs_otm, dacs_max_delta=settings.dacs_max_delta,
        dacs_min_long_price=settings.dacs_min_long_price,
        dacs_min_fast_ratio=settings.dacs_min_fast_ratio,
    )

    # Placeholder in-memory stores so the app is constructible synchronously; swapped
    # for real Redis/Postgres stores inside `lifespan` (on the correct event loop) when
    # PAZ_PERSIST=redis_postgres. Every endpoint below closes over these same names, so
    # the `nonlocal` reassignment is visible everywhere once lifespan startup completes.
    feature_store = InMemoryFeatureStore()
    iv_history = InMemoryIVHistory()
    candidate_repo = InMemoryCandidateRepository()
    bus = InMemoryBus()
    pipeline = Pipeline(feed, feature_store, iv_history, candidate_repo, bus, config,
                        strategies=FOCUS_STRATEGIES)
    scheduler = Scheduler(pipeline, underlyings, interval=interval, today=today)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal feature_store, iv_history, bus, candidate_repo, pipeline, scheduler
        if settings.paz_persist == "redis_postgres":
            feature_store, iv_history, bus, candidate_repo = await _build_real_stores(settings)
            pipeline = Pipeline(feed, feature_store, iv_history, candidate_repo, bus, config,
                                strategies=FOCUS_STRATEGIES)
            scheduler = Scheduler(pipeline, underlyings, interval=interval, today=today)
        if initial_scan:
            await scheduler.scan_all()          # populate before serving
        task = asyncio.create_task(scheduler.run())
        try:
            yield
        finally:
            scheduler.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Paz Rav", version=__version__, lifespan=lifespan)

    async def _features() -> list[dict]:
        out = []
        for u in underlyings:
            f = await feature_store.get(u)
            if f is not None:
                out.append(f.model_dump(mode="json"))
        return out

    async def _candidates(u: str) -> list[dict]:
        return [candidate_to_dict(c) for c in await candidate_repo.latest(u, config.top_n)]

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__,
                "underlyings": underlyings, "strategies": list_strategies()}

    @app.get("/api/underlyings")
    def api_underlyings() -> dict:
        return {"underlyings": underlyings}

    @app.get("/api/state")
    async def api_state() -> dict:
        cands = {u: await _candidates(u) for u in underlyings}
        return {"features": await _features(), "candidates": cands}

    @app.get("/api/candidates/{underlying}")
    async def api_candidates(underlying: str) -> dict:
        return {"underlying": underlying, "candidates": await _candidates(underlying)}

    @app.get("/api/top")
    async def api_top(n: int = 5) -> dict:
        """The best ``n`` trades PER strategy, across all underlyings.

        Only committee-endorsed candidates ("take"/"caution") are surfaced here — a
        "pass" is the committee explicitly saying not to open this, so it has no place in
        a "best trades to open" list even if its raw score happens to rank well. Returns
        one group per strategy (iron condor, DACS) so each is ranked on its own scale —
        the two don't compete on a single number. Each item carries ``u_idx`` (its rank
        within its underlying) for the payoff/explain calls.
        """
        from paz_rav.agents.analyst import review as analyst_review

        by_strat: dict[str, list[dict]] = {}
        for u in underlyings:
            feature = await feature_store.get(u)
            for i, c in enumerate(await candidate_repo.latest(u, config.top_n)):
                verdict = analyst_review(c, feature)[0]
                if verdict == "pass":
                    continue   # the committee said skip it — don't recommend it
                d = candidate_to_dict(c)
                d["u_idx"] = i
                d["verdict"] = verdict
                by_strat.setdefault(c.strategy, []).append(d)
        for rows in by_strat.values():
            rows.sort(key=lambda d: d["score"], reverse=True)

        groups = [{"strategy": s, "trades": by_strat.get(s, [])[:n]}
                  for s in FOCUS_STRATEGIES if s in by_strat]
        return {"groups": groups}

    @app.get("/api/explain/{underlying}/{idx}")
    async def api_explain(underlying: str, idx: int) -> dict:
        """AI (or fallback) plain-language explanation of a position — clear to a child."""
        from paz_rav.agents import explain
        cands = await candidate_repo.latest(underlying, config.top_n)
        if idx < 0 or idx >= len(cands):
            return {"text": ""}
        return {"text": await explain(cands[idx])}

    @app.get("/api/review/{underlying}/{idx}")
    async def api_review(underlying: str, idx: int) -> dict:
        """Committee review: analyst verdict + rationale, critic's objection, explanation."""
        from paz_rav.agents import review
        cands = await candidate_repo.latest(underlying, config.top_n)
        if idx < 0 or idx >= len(cands):
            return {}
        feature = await feature_store.get(underlying)
        out = await review(cands[idx], feature)
        if feature is not None:
            out["context"] = {"regime": feature.regime, "iv_rank": feature.iv_rank,
                              "rsi": feature.rsi}
        return out

    @app.get("/api/payoff/{underlying}/{idx}")
    async def api_payoff(underlying: str, idx: int) -> dict:
        cands = await candidate_repo.latest(underlying, config.top_n)
        if idx < 0 or idx >= len(cands):
            return {"points": []}
        c = cands[idx]
        strikes = sorted(leg.strike for leg in c.legs)
        eval_date = date.fromisoformat(c.meta["eval_date"]) if "eval_date" in c.meta else None
        sigma = float(c.meta.get("sigma", 0.20))
        lo, hi = strikes[0] * 0.85, strikes[-1] * 1.15
        step = (hi - lo) / 60
        # multi-expiry aware: prices still-alive long legs (correct for DACS), intrinsic
        # for same-expiry legs (iron condor). Falls back to expiry intrinsic if no eval date.
        points = []
        for i in range(61):
            s = lo + i * step
            pnl = (structure_pnl(c.credit, c.legs, s, eval_date, config.r, sigma)
                   if eval_date else pnl_at_expiry(c, s))
            points.append({"price": round(s, 2), "pnl": round(pnl, 2)})
        return {"underlying": underlying, "strikes": strikes, "points": points}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({
            "type": "snapshot",
            "features": await _features(),
            "candidates": {u: await _candidates(u) for u in underlyings},
        })

        async def forward(channel: str, msg_type: str) -> None:
            async for payload in bus.subscribe(channel):
                await websocket.send_json({"type": msg_type, "data": payload})

        tasks = [
            asyncio.create_task(forward(CH_FEATURES, "feature")),
            asyncio.create_task(forward(CH_CANDIDATES, "candidates")),
        ]
        try:
            while True:
                await websocket.receive_text()   # keep the socket open
        except WebSocketDisconnect:
            pass
        finally:
            for t in tasks:
                t.cancel()

    # Serve the built dashboard if present (after `npm run build` in web/).
    if _WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=_WEB_DIST / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(_WEB_DIST / "index.html")

    return app


app = create_app()
