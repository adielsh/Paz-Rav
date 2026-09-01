# Architecture

How Paz Rav is put together, and — more usefully — *why*. If you only read one section, read
the next one.

## The line down the middle

There is exactly one architectural rule here, and everything else follows from it:

> **Python computes. The AI reasons over what Python computed. Never the other way round.**

Greeks, implied vol, probability of profit, scores, P&L — all of it comes out of `quant/`,
`analytics/`, `strategies/`, `backtest/`. Pure functions, with tests. A language model handed
*"P&L is 48% of max, 9 days left, spot is drifting toward your short strike"* can say
something genuinely useful about it. A language model asked to *compute* that P&L will, some
day, be confidently wrong — and you won't know which day. So it never gets the chance.

Everything below exists to keep that line clean.

## One pipeline, two callers

`Pipeline.run_once()` (`src/paz_rav/pipeline.py`) is the whole engine in one function:

```
chain → analytics.analyze()  → FeatureStore + IVHistory
      → builder.build()      → CandidateRepository
      → exit_manager.sweep() → flags open positions (never closes them)
```

The scheduler calls it on a timer. The backtester replays history through it. Same code both
times — which is the only reason backtest results say anything at all about live behaviour.
Two separate implementations would drift apart within a month and nobody would notice.

## Why one process, not seven

It ships as a **modular monolith**: strict module boundaries (`adapters`, `analytics`,
`strategies`, `builder`, `agents`, `positions`, `store`, `api`), one deployable. For a solo
project, seven containers buy you nothing but seven things to restart.

The boundaries are real, though, so extraction is cheap when there's a reason. The rule:
**extract only on a trigger you've actually hit.**

| Candidate for extraction | The trigger | Status |
|---|---|---|
| Advisor (close-timing debate) | Slow and LLM-bound — scales differently from the tick loop | extracted |
| Real-time engine (feed + analytics) | Must never drop a tick because the UI restarted | in-process |
| API / web server | Redeploy the dashboard without touching the engine | in-process |

Ceiling: three deployables, and only when it hurts.

### The one that did get extracted

The close-timing debate lives in `services/advisor` as its own container — same image,
different entrypoint (`:8001`), one endpoint (`POST /advise` → the verdict). It earned that:
slow, LLM-bound, and already a pure function of a `Situation` the monolith computes, so the
cut was clean — no state, no database.

It's never a hard dependency. `close_advisor._resolve_debate()` is a small circuit breaker —
remote → in-process LLM debate → deterministic fallback — so a dead advisor doesn't take the
dashboard with it, and clearing `ADVISOR_URL` runs the identical debate in-process. That's the
real payoff of module boundaries: moving a room out of the house was a config flip, not a
rewrite.

## Why two agents, not zero and not seven

The always-on filter is **deterministic**: `agents/analyst.py` proposes a verdict
(take / caution / pass), `agents/critic.py` argues the bear case. No LLM call — so it runs on
every candidate on every scan for free, and it can be backtested. `agents/graph.py` wraps the
pair in a real LangGraph loop (a severe objection sends a "take" back to the Analyst for one
revision), falling back to a sequential pass in `committee.py` when LangGraph isn't installed.

- **Not zero agents** — weighing conflicting context ("IV rank borderline, but FOMC in three
  days") is exactly what fixed rules are bad at.
- **Not one** — a model that proposes and critiques itself in the same breath just agrees
  with itself at greater length.
- **Not seven** — Regime/Risk/PM agents would re-decide what deterministic rules already
  cover, at real cost. They'd earn their place managing a correlated portfolio.

`agents/explainer.py` is a fixed template, not a model. It used to be Haiku, but prose
*containing numbers* is precisely where a small model can quietly break the rule at the top
of this page.

## The close-timing debate — where a model finally decides

"Should I close now?" is genuinely hard: 48% of max profit is good, 9 DTE with spot drifting
toward your short strike is not, and no single fixed rule weighs those against each other
well. So this is the one place a language model reasons *toward a decision*.

Three real Claude calls, run as a LangGraph graph:

```
analyst → critic → decider → (confidence < 0.5 and not yet revised?
                              back to the analyst with the objection, once) → done
```

The Critic's job is *איפכא מסתברא* — argue the opposite of whatever the Analyst said, so the
overlooked risk surfaces. The Decider returns `hold | close | reduce` plus a confidence. This
is where LangGraph actually earns its keep: language-model nodes, a branching graph, a real
conditional loop. A single agent wouldn't need a framework.

Two things keep it honest. **Every number is pre-computed** — `build_situation()` gathers
mark-to-market P&L, DTE, distance-to-stop, IV rank, regime and recent move, and forced
tool-use (structured JSON) means a model *cannot* return free-form prose or a figure of its
own, only a stance plus reasons citing what it was handed. And it's **advisory only**: it
never closes anything, and a cache keyed on a coarse market-state signature means refreshing
the dashboard is free — the debate re-runs only when something material moved, or when you
click "check now".

`agents/open_advisor.py` is the same machinery pointed at *entry* instead of exit. Both
degrade all the way down: no `langgraph` → sequential pass; no `ANTHROPIC_API_KEY` →
deterministic rule-based "debate". The dashboard always answers, and tests stay offline.

## Two features waiting for data

Both of these are finished, tested code that does approximately nothing until you've closed a
few dozen real trades. Worth knowing before you go looking for their value.

**Case memory** (`store/case_memory.py`) stores every closed position as a
`(vector, real outcome)` pair, so the debate can recall how similar trades ended: "trades that
reached a state like this one ended 4 out of 5 in profit." The choice worth noticing is that
**the vector isn't an LLM embedding** — `vectorize()` builds it from numbers the quant core
already computed (normalized DTE, P&L %, distance-to-stop, IV rank, RSI, recent move, plus
strategy and regime one-hots), and retrieval is plain cosine similarity over pgvector. So the
"embedding" is just the computed numbers: reproducible, testable offline, no embedding API,
and the line at the top of this page holds. No pgvector → in-memory scan; no cases yet → the
debate runs without recall.

**Reflection** (`agents/reflection.py`) steps back over the *whole* closed-trade history and
suggests what to tune — advisory, never self-tuning. `aggregate_stats()` computes every
statistic in Python; the model only interprets. It never sees raw rows, only fixed-size
aggregates plus a window of recent reflections, so it costs the same at 10 closed trades or
10,000 — and below `MIN_SAMPLE` it says "not enough data yet" instead of finding patterns in
noise.

Each reflection is *stored* in Postgres (the product reads it back — the filing cabinet) and
the *run* is *traced* to Langfuse (the security camera). You don't retrieve business documents
from CCTV footage.

## Storage, swapped behind Protocols

`store/base.py` and `positions/base.py` define `Protocol`s: `FeatureStore`, `IVHistoryStore`,
`CandidateRepository`, `PositionRepository`. Each has an in-memory implementation (the
default, and what tests use) and a real one behind `PAZ_PERSIST=redis_postgres` — features, IV
history and the bus move to Redis; candidates and positions to Postgres.

> Redis is *what's true now*. Postgres is *what happened*. The desk and the filing cabinet.

## Concurrency

| Work | Worker | Why |
|---|---|---|
| I/O — feed, API, dashboard push | one `asyncio` loop | never blocks on the network |
| CPU — greeks, IV fit, Monte-Carlo | process pool | bypasses the GIL |
| LLM calls | async + `Semaphore(k)` | network-bound; caps spend and rate limits |

## Stack

Python 3.12, FastAPI, Pydantic, asyncio; numpy/scipy/py_vollib/polars (with pure-Python
fallbacks in `quant/`, so tests need none of them); Redis; Postgres + pgvector; React +
TypeScript + Recharts + Tailwind; Docker Compose. On the AI side: the Anthropic SDK directly,
LangGraph only for the debate loops, Langfuse for tracing.

Feeds sit behind one `MarketData` adapter — yfinance (free, delayed, dev) and Interactive
Brokers (stubbed, not wired). Swapping is a one-line change.

Deliberately *not* used: RabbitMQ (an asyncio/Redis queue is plenty solo), the broad LangChain
framework, MCP. Deferred until a real trigger: Kafka, Kubernetes, applied Terraform.

## Repo layout

```
src/paz_rav/
  adapters/    market-data ports (yfinance / IBKR)        Adapter
  quant/       greeks · implied_vol · pop · valuation     pure functions — the accuracy core
  analytics/   iv · regime · rsi · features               chains → one Feature
  strategies/  base + iron_condor + dacs + registry       Strategy + Factory
  builder/     annotate + enumerate + rank
  agents/      analyst · critic · graph · explainer       + the LLM debates
  positions/   base + exit_rules + exit_manager           advisory-only lifecycle
  services/    advisor/ — the one extracted service
  store/       base + memory / redis / postgres           Repository
  bus/         channels for live push                     Observer
  contracts/   shared Pydantic schemas
  api/         FastAPI + WebSocket
tests/         pytest, pure — no infra, no network
scripts/       runnable demos (pipeline / builder / backtest)
web/           React dashboard
infra/         Terraform scaffold — never applied
```

Patterns pulling their weight: **Strategy** (interchangeable structures), **Factory** (build
by name), **Adapter** (swap vendor), **Repository** (swap storage), **Observer** (live push).
