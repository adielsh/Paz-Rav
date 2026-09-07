# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is — a monorepo with two halves

This repo holds two systems that share a database, a network and a broker vendor. Know
which half you are in before you change anything.

| | **The engine** — `src/paz_rav/` | **The console** — `apps/console/` |
|---|---|---|
| Job | Scans ~9 underlyings, ranks Iron Condor + DACS candidates, reasons about them | Trades one strategy (SPX iron condor) on IBKR for real |
| Trades? | **No.** No broker connection, no order route. Advisory only | **Yes.** `trading-core` is the only service that can place an order |
| UI | `web/` — its own dashboard, on :8010, pending migration | `apps/console/frontend/` — **the primary UI**, on :8080 |
| Data | yfinance (delayed) or a fixture. `adapters/ibkr.py` is still a stub | Live IB gateway via `ib_async` |
| DB schema | `engine` | `public` |
| Guidance | this file | `apps/console/CLAUDE.md` |

**The console frontend never calls the engine directly.** It goes through
`apps/console/api/app/engine_proxy.py`, a read-only GET proxy that sits behind the console's
session cookie — the engine's own Firebase gate is switched off precisely because that proxy
is its only door. Don't add an nginx route around it.

Ports (all bound to `127.0.0.1`): console **8080** · console API 8000 · engine 8010 ·
advisor 8001 · Grafana 3000 · Postgres 5432 · Redis 6379.

The rest of this file is about **the engine**. Full rationale lives in
`docs/ARCHITECTURE.md`, running/deployment in `docs/DEPLOYMENT.md`, and phase status in
`docs/ROADMAP.md` — read them before making architectural changes; this file only covers
what you need to be productive day to day.

### The engine, specifically

Paz Rav — a real-time options strategy engine for **Iron Condor** and **DACS 1.0** (a
diagonal adaptive calendar spread). It scans a fixed universe of underlyings, ranks
candidate positions with a deterministic quant core, runs them through an AI judgment
layer (Analyst + Critic + Explainer), and serves a live dashboard for opening/closing
paper positions.

**Core design rule, non-negotiable:** every greek, IV, price, POP, and P&L comes from
deterministic Python (`src/paz_rav/quant/`, `analytics/`, `strategies/`, `backtest/`). LLMs
(`src/paz_rav/agents/`) only ever reason over already-computed structured data — they never
compute a number themselves. Don't blur this line when adding features.

## Commands

### Run everything (recommended)
```bash
docker compose up -d --build          # the WHOLE monorepo, one command
# → http://127.0.0.1:8080   the console (start here)
# → http://127.0.0.1:8010   the engine's own dashboard
```
There is exactly one `docker-compose.yml`, at the repo root — it drives both halves.
Rebuild one service after a change: `docker compose up -d --build engine` (or `api`,
`frontend`, `trading-core`).

Two things about that compose file that will cost you an afternoon if you miss them:

- **`name: pazrav` is pinned at the top.** Compose otherwise derives the project name from
  the directory, and the volumes were created under a different one. Removing it points
  `condor-pgdata` at a new, empty volume and looks exactly like the database was wiped.
- **`infra/postgres/init/` only auto-runs on an empty data directory.** On an existing
  database apply it by hand once:
  `docker compose exec postgres psql -U condor -d condor -f /docker-entrypoint-initdb.d/10-engine-schema.sql`
  On Git Bash for Windows, prefix that with `MSYS_NO_PATHCONV=1`. Until it is applied the
  engine dies with `password authentication failed for user "paz"` — the intended failure:
  it never reaches a `CREATE TABLE`, so it cannot leak tables into the console's `public`
  schema. `docs/MONOREPO.md` also covers the collation reindex after the image swap.

`PAZ_DATA` selects the engine's feed: `yfinance` (delayed, the default) or `fixture`
(offline demo data).

### Backend (Python), running from source
```bash
pip install -e ".[feeds,dev]"                    # core + free data feed + test tooling
pip install -e ".[quant,agents]"                 # optional: numeric stack, AI layer deps
python -m pytest                                 # engine suite (pure, no infra/network)
python -m pytest tests/test_dacs.py              # a single file
python -m pytest tests/test_dacs.py::test_name   # a single test
UNDERLYINGS=SPY uvicorn paz_rav.api.app:app --port 8000 --reload   # API only, in-memory stores
```
`pyproject.toml` extras: `quant` (numpy/scipy/py_vollib/polars/duckdb — the pure-Python
fallbacks in `quant/` mean tests never need these), `feeds` (yfinance/ib_async), `agents`
(anthropic/langgraph/langfuse), `dev` (pytest/ruff/mypy/fakeredis), `console` (only to run
the console's suite from here).

`python -m pytest` deliberately runs the **engine suite only** — it needs no infrastructure,
no network and no extra installs, and that property is worth keeping. Both halves at once:
```bash
pip install -e ".[console]"
python -m pytest tests apps/console/trading-core/tests    # 106 + 15
```

Real persistence instead of in-memory stores (needs `docker compose up -d` for Postgres/Redis first):
```bash
PAZ_PERSIST=redis_postgres UNDERLYINGS=SPY,QQQ uvicorn paz_rav.api.app:app --port 8000
```

### Frontend

Two of them. `apps/console/frontend/` is the primary UI — see `apps/console/CLAUDE.md`.
`web/` below is the engine's own dashboard, still served by the engine on :8010 until its
pages are migrated into the console.

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
Don't trust `tsc`/`pytest` alone for anything touching an API or a dashboard — rebuild and
curl it:
```bash
docker compose up -d --build engine
curl -s http://127.0.0.1:8010/health
curl -s "http://127.0.0.1:8010/api/top?n=5"
docker inspect --format='{{.State.Health.Status}}' condor-engine   # → healthy
```
If the change touches the console, do the same there — and check the engine page, which is
the one surface that spans both halves:
```bash
docker compose up -d --build api frontend
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/engine/top      # → 401 without a session cookie
```
Then open http://127.0.0.1:8080 and walk the pages. **The regression that matters most:
stop the engine (`docker compose stop engine`) and confirm every other page still works** —
`/ideas` must show its offline state and nothing else may break.

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

### Storage is swappable behind Protocols
`store/base.py` and `positions/base.py` define `Protocol`s (`FeatureStore`, `IVHistoryStore`,
`CandidateRepository`, `PositionRepository`). Each has an in-memory implementation used by
default and in tests, plus real Redis/Postgres implementations (`store/redis_store.py`,
`store/postgres_store.py`, `store/postgres_position_repo.py`) used when
`PAZ_PERSIST=redis_postgres` — features/IV-history/bus move to Redis, candidates and
positions to Postgres. `PostgresPositionRepository.save()` is an upsert keyed on the
position's UUID (a position is mutated over its life: alert set/cleared, then closed) —
`PostgresCandidateRepository.save()` is a plain insert (candidates are always fresh per
scan). Follow whichever pattern matches when adding a new Postgres-backed store.

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
backtest. `agents/explainer.py` is also deterministic — a fixed, exact template (it used to
call Claude Haiku, but a small model writing prose *containing numbers* risks misstating
them, the one thing this project forbids, so it's a template now). `agents/graph.py` wraps
Analyst↔Critic in a real LangGraph loop (a severe Critic objection can send a "take" back to
the Analyst for one revision) when `langgraph` is installed, falling back to a plain
sequential call in `committee.py` otherwise — both paths return the same shape. **The one
place real LLMs actually decide is `agents/close_advisor.py`** — the close-timing debate
(Analyst→Critic→Decider on a LangGraph graph with a conditional revision loop); models only
weigh already-computed numbers there, never restate them as prose. Langfuse tracing is
best-effort and silently no-ops without `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`.

**Contract multiplier:** every dollar figure on a `Candidate`/`Position` (credit, max_profit,
max_loss, realized/unrealized P&L) is **per share**; a US options contract is ×100. The
frontend `format.ts` (`usdContract`/`usdContractSigned`) and `explainer.py` multiply by 100
for display — strikes/breakevens are price levels and are NOT multiplied. Iron-condor wings
are equalized to the same dollar width (the wider side sets the collateral, so the narrower
side is widened to match) in `strategies/iron_condor.py`.

### Positions are advisory-only by design
`positions/exit_manager.sweep()` never closes a position — it only sets `Position.alert`
(the real fill happens at the user's broker, not in this system). Closing is always a
`close_position(...)` call carrying the *actual* net price the user reports; `realized_pnl`
is computed directly from that (`entry_credit + exit_credit`), never modeled. When a
position closes, its outcome is scored back onto the exact Langfuse trace the opening
committee decision produced (`Position.langfuse_trace_id`) — this is the closed feedback
loop described in `docs/ROADMAP.md`'s Phase 3. Positions persist to Postgres (not just
in-memory) via `PostgresPositionRepository`, following the same "build inside `lifespan`"
rule as the other Postgres-backed stores.

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
