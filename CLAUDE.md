# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Paz Rav — a real-time options strategy engine for **Iron Condor** and **DACS 1.0** (a
diagonal adaptive calendar spread). It scans a fixed universe of underlyings, ranks
candidate positions with a deterministic quant core, runs them through an AI judgment
layer (Analyst + Critic + Explainer), and serves a live dashboard for opening/closing
paper positions. Full rationale and phased roadmap live in `README.md` — read it before
making architectural changes; this file only covers what you need to be productive day to
day.

**Core design rule, non-negotiable:** every greek, IV, price, POP, and P&L comes from
deterministic Python (`src/paz_rav/quant/`, `analytics/`, `strategies/`, `backtest/`). LLMs
(`src/paz_rav/agents/`) only ever reason over already-computed structured data — they never
compute a number themselves. Don't blur this line when adding features.

## Commands

### Run everything (recommended)
```bash
docker compose up -d --build          # Postgres + Redis + the app, one command
# → http://localhost:8000
```
Rebuild just the app after a backend or frontend change: `docker compose up -d --build app`.
Uses `PAZ_DATA=fixture` by default (offline demo data); set `PAZ_DATA=yfinance` in the
shell before `up` for live delayed quotes.

### Backend (Python), running from source
```bash
pip install -e ".[feeds,dev]"                    # core + free data feed + test tooling
pip install -e ".[quant,agents]"                 # optional: numeric stack, AI layer deps
python -m pytest                                 # full suite (pure, no infra/network)
python -m pytest tests/test_dacs.py              # a single file
python -m pytest tests/test_dacs.py::test_name   # a single test
UNDERLYINGS=SPY uvicorn paz_rav.api.app:app --port 8000 --reload   # API only, in-memory stores
```
`pyproject.toml` extras: `quant` (numpy/scipy/py_vollib/polars/duckdb — the pure-Python
fallbacks in `quant/` mean tests never need these), `feeds` (yfinance/ib_async), `agents`
(anthropic/langgraph/langfuse), `dev` (pytest/ruff/mypy/fakeredis).

Real persistence instead of in-memory stores (needs `docker compose up -d` for Postgres/Redis first):
```bash
PAZ_PERSIST=redis_postgres UNDERLYINGS=SPY,QQQ uvicorn paz_rav.api.app:app --port 8000
```

### Frontend (web/)
```bash
cd web && npm install
npm run dev             # Vite dev server, proxies /api and /ws to :8000 (run the backend separately)
npm run build            # tsc -b && vite build → web/dist, served by the FastAPI app
```
`tsconfig.json` has `noUnusedLocals`/`noUnusedParameters` on — an unused import fails the
build, not just lint.

### CLI demos (no browser needed)
```bash
PYTHONPATH=src python scripts/pipeline_demo.py SPY     # full pipeline on real yfinance data
PYTHONPATH=src python scripts/builder_demo.py SPX      # analytics → builder only
PYTHONPATH=src python scripts/backtest_demo.py         # walk-forward backtest, both strategies
PYTHONPATH=src python scripts/make_fixture.py          # regenerate tests/fixtures/sample_market.json
```

### Verifying a change end-to-end
Don't trust `tsc`/`pytest` alone for anything touching the API or dashboard — rebuild and
curl it:
```bash
docker compose up -d --build app
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/api/top?n=5"
```
`docker inspect --format='{{.State.Health.Status}}' paz-rav-app-1` should read `healthy`
(the image has a `HEALTHCHECK` hitting `/health`).

## Architecture

### The pipeline (the one path everything flows through)
`Pipeline.run_once()` in `pipeline.py` is the seam the scheduler drives on a loop and the
backtester replays — both call the *same* code, which is what guarantees backtest/live
parity:
```
MarketData feed → analytics.analyze() → FeatureStore + IVHistory (+ publish to bus)
                → builder.build() → CandidateRepository (+ publish to bus)
                → positions.exit_manager.sweep() → flags (never auto-closes) open positions
```
`api/app.py`'s `create_app()` wires a `Scheduler` (a timer, not a service) around this and
exposes it over FastAPI + a WebSocket that fans out the bus.

### Storage is swappable behind Protocols, not swapped in practice yet
`store/base.py` and `positions/base.py` define `Protocol`s (`FeatureStore`, `IVHistoryStore`,
`CandidateRepository`, `PositionRepository`). Each has an in-memory implementation used by
default and in tests, plus real Redis/Postgres implementations
(`store/redis_store.py`, `store/postgres_store.py`) used when `PAZ_PERSIST=redis_postgres`.
**Positions currently stay in-memory even in that mode** — only features/IV-history/candidates
move to Redis/Postgres. If you add persistence for positions, follow the existing pattern.

Building the Postgres pool must happen inside FastAPI's `lifespan` coroutine, not at
`create_app()` time — `asyncpg` binds its pool to the event loop that creates it, and a
throwaway `asyncio.run()` before uvicorn starts its own loop causes every later query to
hang silently. `app.py`'s `_build_real_stores()` + the `nonlocal` reassignment inside
`lifespan` is the fix; don't reintroduce the bug by constructing stores at module/function
scope outside that coroutine.

### Adding a strategy
`strategies/base.py` defines `OptionStrategy` (just `name` + `enumerate(...)`) and
`BuildConfig`/`MarketContext`/`AnnotatedQuote`. `strategies/registry.py` is a Factory —
`@register` a class and it's available via `make_strategy(name)`; `FOCUS_STRATEGIES` in that
file controls which ones the API actually surfaces (currently `iron_condor` + `dacs` only —
`diagonal`/`double_diagonal` exist and pass tests but aren't user-facing). `builder/core.py`
annotates a raw chain with greeks/IV/liquidity once and hands the same `AnnotatedQuote` list
to every registered strategy — don't duplicate that computation inside a strategy.
`strategies/scoring.py`'s `finalize()` prices any structure via the shared digital-twin
valuation (`quant/valuation.py`) and applies `regime_fit` — this is what makes strategies
with wildly different shapes (single-expiry condor vs. multi-expiry DACS) comparable on one
score.

### The AI layer is intentionally two agents, not a big committee
`agents/analyst.py` (verdict: take/caution/pass) and `agents/critic.py` (the adversarial
bear case) are deterministic and rule-based — no LLM call, so they're cheap to test and
backtest. `agents/explainer.py` is the only place an LLM (Claude, via `ANTHROPIC_API_KEY`)
is actually called, and only to phrase a plain-language summary — it never decides
anything. `agents/graph.py` wraps Analyst↔Critic in a real LangGraph loop (a severe Critic
objection can send a "take" back to the Analyst for one revision) when `langgraph` is
installed, falling back to a plain sequential call in `committee.py` otherwise — both paths
return the same shape. Langfuse tracing (`graph.py`'s `_maybe_trace`) is best-effort and
silently no-ops without `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`.

### Positions are advisory-only by design
`positions/exit_manager.sweep()` never closes a position — it only sets `Position.alert`
(the real fill happens at the user's broker, not in this system). Closing is always a
`close_position(...)` call carrying the *actual* net price the user reports; `realized_pnl`
is computed directly from that (`entry_credit + exit_credit`), never modeled. When a
position closes, its outcome is scored back onto the exact Langfuse trace the opening
committee decision produced (`Position.langfuse_trace_id`) — this is the closed feedback
loop described in the README's Phase 3.

### Frontend
`web/src/theme.ts` and `web/tailwind.config.js` hold the same color palette in two places
deliberately (Tailwind's config can't import a TS module) — keep them in sync by hand.
`lib.ts`'s `strategyColor()`/`strategyLabel()` and `Icon.tsx` (a small hand-rolled SVG set —
no emoji as structural icons) are shared across `Suggestions.tsx`, `Positions.tsx`, and
`TradeDetails.tsx`; `LegLadder.tsx` is the one place leg display logic lives, reused in both
the suggestion cards and the position cards for visual consistency. The suggestion/position
cards use `role="button" tabIndex={0}` with manual `onKeyDown` (not a native `<button>`)
because each card contains a real nested `<button>` (Open/Close) — nesting a `<button>`
inside a `<button>` is invalid HTML, so don't "simplify" this back to a native button.

### Data contracts crossing module boundaries
`contracts/__init__.py` (Pydantic: `OptionQuote`, `Feature`, `UnderlyingQuote`) and
`strategies/base.py` (`Candidate`, `Leg`) are the shared vocabulary every module agrees on.
`store/serialize.py` has the JSON (de)serialization for `Candidate`/`Feature` — `Leg` carries
an optional `expiry`/`iv` (used by multi-expiry strategies like DACS), so don't use
`dataclasses.asdict` directly on a `Candidate` containing `date` objects; use the functions
in `serialize.py`.
