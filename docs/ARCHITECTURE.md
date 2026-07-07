# Architecture

See the [system diagram and flow chart in the README](../README.md#system-at-a-glance)
for the visual overview — this page is the reasoning behind them.

## The pipeline

`Pipeline.run_once()` (`src/paz_rav/pipeline.py`) is the one function that does
everything the diagrams show — the scheduler drives it on a loop live, and the
backtester replays history through the *same* function, which is what guarantees
live/backtest parity:

1. **Deterministic engine (no AI).** Ingest a chain, compute features (greeks, IV rank,
   regime, RSI), enumerate and score Iron Condor + DACS candidates.
2. **Two-agent judgment (AI).** Analyst proposes a verdict (take / caution / pass);
   Critic argues the bear case. A severe objection sends a "take" back to the Analyst
   for one revision — a real LangGraph loop, not two sequential calls.
3. **Positions + learning loop.** Opening a position captures the committee's Langfuse
   trace id. The Exit Manager never closes a position — it only flags it, since the real
   fill happens at your broker. Confirming the close with the real price scores the
   realized P&L back onto that trace.

## Why a modular monolith, not microservices

Ships as **one process**, deliberately — for a solo project, running 7 containers is
pure ops cost with no benefit.

- **Modules are strict** (`adapters`, `analytics`, `strategies`, `builder`, `agents`,
  `positions`, `store`, `api`) — clean boundaries, so extraction later is cheap.
- **Deployment isn't split.** Modules call each other in-process; the same boundaries
  become network calls only if a module is actually extracted.
- The **scheduler** is an in-process timer and the **backtester** a run mode — neither is
  an always-on server, despite looking like one in the diagram.

**Extract only on a real trigger:**

| Extract | Trigger |
|---|---|
| Real-time engine (feed + analytics) | Must never drop a tick / be disturbed by a UI restart or slow AI call |
| API / web server | Want to redeploy the dashboard without touching the trading engine |
| Committee (LLM agents) | Agent calls are slow/expensive; want to scale independently |

At most three deployables, only when the pain is real.

## Why exactly two agents

- **Not zero** — a pure rule engine can't weigh conflicting contextual signals ("IV rank
  borderline, but FOMC in 3 days"). That synthesis plus a written rationale is real
  value.
- **Not one** — a model that proposes *and* critiques itself in one breath is
  overconfident. Splitting proposal from critique catches more bad trades.
- **Not more** — extra agents (Regime, Risk, PM) add cost for judgment deterministic
  rules already cover; they'd only earn their place managing a correlated portfolio or
  selling signals.

**LangGraph** manages exactly the Analyst↔Critic loop — nothing else from LangChain is
used. **Langfuse** traces every decision and lets you score the realized outcome back
onto it — the difference between a bot that picks trades and a system that learns which
of its own judgments were good.

## The close-timing debate — where a real LLM finally decides

The opening Analyst/Critic are deterministic rule code (no LLM) — cheap to test and
backtest. The **close-timing advisor** (`agents/close_advisor.py`) is different, and
deliberately so: it's the one place a language model is trusted to *reason toward a
decision*, because "should I close now?" weighs genuinely conflicting, contextual signals
("48% of max profit, but 9 DTE and spot drifting toward the short") that a single fixed
rule can't.

When the user asks, **three real Claude calls** run as a LangGraph graph:

```
analyst → critic → decider → (if the Decider's confidence < 0.5 and we haven't
                              revised yet: loop back to the Analyst with the Critic's
                              objection, once) → done
```

- **Analyst** — reads the situation, argues hold vs. close.
- **Critic** — the *איפכא מסתברא*: argues the opposite of the Analyst, to surface the
  overlooked risk (or opportunity).
- **Decider** — weighs both, returns `hold | close | reduce` + confidence + rationale.

This is where **LangGraph genuinely earns its place** — it orchestrates *language-model*
nodes (not rule nodes) through a branching graph with a real conditional loop; a single
agent wouldn't need one. The debate degrades to a plain sequential pass if `langgraph`
isn't installed, and to a deterministic rule-based "debate" if there's no
`ANTHROPIC_API_KEY` — so the dashboard always answers and the tests stay offline.

Two invariants keep it honest:

1. **Every number is pre-computed in Python** (`build_situation()` gathers mark-to-market
   P&L, DTE, distance-to-stop, IV rank, regime, recent move). The models only weigh
   numbers; **forced tool-use** (structured JSON output) means a model literally cannot
   return free-form prose or a made-up figure — only a stance + reasons that cite the
   given numbers.
2. **Advisory only**, like the Exit Manager — it never closes anything; the real fill is
   at the broker. Cost is bounded by a cache keyed on a coarse market-state signature, so
   ordinary dashboard refreshes are instant and only a material change (or an explicit
   "check now") re-runs the debate. Each debate is traced to Langfuse on the position's
   original opening trace.

## Concurrency model

| Work | Worker | Why |
|---|---|---|
| I/O — feed, API, dashboard push | single `asyncio` event loop | never blocks on the network |
| CPU — greeks, IV fit, Monte-Carlo | process pool | bypasses the GIL |
| LLM — Analyst, Critic | async + `Semaphore(k)` | network I/O; caps spend and rate limits |

## Tech stack

**Essential** — Python 3.12 / FastAPI / Pydantic / asyncio, numpy/scipy/py_vollib/polars
(the quant core also has pure-Python fallbacks, so tests need none of these), Redis (hot
state + pub/sub), Postgres (candidates, positions), React + TypeScript + Recharts +
Tailwind, Docker Compose.

**AI layer** — Anthropic SDK (direct calls, no framework), LangGraph (the Analyst↔Critic
loop only), Langfuse (tracing + scoring).

**Deferred, on a real trigger** — Kafka (only if Redis Streams stops being enough at
scale), pgvector (case-memory, once there's a real body of outcomes), Kubernetes /
Terraform-in-anger (see [`docs/DEPLOYMENT.md`](DEPLOYMENT.md)).

**Deliberately not used** — RabbitMQ (an asyncio/Redis queue suffices solo), the broad
LangChain framework, MCP (plain typed functions give the same shared code path with less
indirection).

**Data feeds** (behind one `MarketData` Adapter): yfinance (free, delayed, dev) and
Interactive Brokers (real-time, stubbed but not wired). Swapping is a one-line change.

> **Redis vs. Postgres, in one line:** Redis is *"what's true now"*; Postgres is *"what
> happened."* Redis is the desk, Postgres is the filing cabinet.

## Repo layout

```
Paz-Rav/
  src/paz_rav/
    adapters/     market-data ports (yfinance/IBKR)       Adapter
    quant/        greeks · implied_vol · pop · valuation   pure functions — the accuracy core
    analytics/    iv · regime · rsi · features             turns chains into one Feature
    strategies/   base + iron_condor + dacs + registry     Strategy + Factory
    builder/      annotate + enumerate + rank
    agents/       analyst · critic · graph · explainer     the two-agent loop (LangGraph)
    positions/    base + exit_rules + exit_manager         advisory-only lifecycle
    store/        base + memory/redis/postgres             Repository
    bus/          channels for live push                   Observer
    contracts/    shared Pydantic schemas
    api/          FastAPI + WebSocket
  tests/          pytest suite (pure, no infra)
  scripts/        runnable demos (pipeline/builder/backtest)
  web/            React dashboard
  infra/terraform/  AWS scaffold (not applied — see docs/DEPLOYMENT.md)
```

Patterns doing the work: **Strategy** (interchangeable structures), **Factory** (build by
name), **Adapter** (swap vendor), **Repository** (swap storage), **Observer** (live push).
