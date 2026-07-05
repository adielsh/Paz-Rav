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
from paz_rav.config import get_settings
from paz_rav.pipeline import Pipeline
from paz_rav.scheduler import Scheduler
from paz_rav.store.memory import (
    InMemoryCandidateRepository,
    InMemoryFeatureStore,
    InMemoryIVHistory,
)
from paz_rav.store.serialize import candidate_to_dict
from paz_rav.strategies import BuildConfig, list_strategies

log = logging.getLogger("paz_rav.api")
_WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def create_app(
    *, feed=None, underlyings: list[str] | None = None,
    interval: float = 60.0, initial_scan: bool = True,
    config: BuildConfig | None = None, today: date | None = None,
) -> FastAPI:
    settings = get_settings()
    if feed is None:
        from paz_rav.adapters import YFinanceMarketData
        feed = YFinanceMarketData()
    underlyings = underlyings or settings.underlying_list
    config = config or BuildConfig(short_deltas=(16.0, 25.0), wing_widths=(5.0, 10.0),
                                   min_open_interest=10, max_rel_spread=0.6, top_n=6)

    feature_store = InMemoryFeatureStore()
    iv_history = InMemoryIVHistory()
    candidate_repo = InMemoryCandidateRepository()
    bus = InMemoryBus()
    pipeline = Pipeline(feed, feature_store, iv_history, candidate_repo, bus, config)
    scheduler = Scheduler(pipeline, underlyings, interval=interval, today=today)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    @app.get("/api/payoff/{underlying}/{idx}")
    async def api_payoff(underlying: str, idx: int) -> dict:
        cands = await candidate_repo.latest(underlying, config.top_n)
        if idx < 0 or idx >= len(cands):
            return {"points": []}
        c = cands[idx]
        lo, hi = min(c.breakevens) * 0.92, max(c.breakevens) * 1.08
        step = (hi - lo) / 60
        points = [{"price": round(lo + i * step, 2),
                   "pnl": pnl_at_expiry(c, lo + i * step)} for i in range(61)]
        return {"underlying": underlying,
                "strikes": sorted(leg.strike for leg in c.legs),
                "points": points}

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
