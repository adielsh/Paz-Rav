# Paz Rav — 2026 Upgrade Plan

> Detailed version (English). Short version: [`UPGRADE-2026-simple.en.md`](UPGRADE-2026-simple.en.md) ·
> עברית: [`UPGRADE-2026.he.md`](UPGRADE-2026.he.md)

---

## 1. Why

Paz Rav today is a genuinely good project. The architecture is clean: a modular monolith,
a `Protocol` behind every storage layer, an iron rule (every number is computed in Python;
the LLM only weighs numbers), and a graceful-degradation ladder at every level. 106 tests
pass; the whole stack comes up with one command.

Three things separate it from a flagship project:

1. **The AI layer was written against a 2025 API**, and it has no measurement at all. It
   also carries a bug that silently kills all tracing — which means nothing about decision
   quality can be proven.
2. **The quant core is precise but shallow** — a single flat sigma, no smile, no term
   structure.
3. **The backtest doesn't actually test the system** — it's a P&L aggregator that never
   runs the pipeline and never applies the exit rules.

**The goal:** first get the project to a place that impresses a senior engineer (AI depth,
measurement, observability), and in the same motion build a base correct enough to trust
with real money in the next phase.

---

## 2. Findings from the review

Everything below was found in the code itself — not estimated.

| # | Finding | File | Severity |
|---|---|---|---|
| 1 | `langfuse>=2.0` is declared in `pyproject.toml`, but the code calls the **v3** API (`create_trace_id`, `create_event(trace_context=)`, `create_score(data_type=)`). All of it is wrapped in `except Exception: pass` → **tracing is dead silently** | `pyproject.toml`, `agents/*.py`, `positions/exit_manager.py:70` | 🔴 |
| 2 | No `messages.create` is ever recorded as a generation. No prompt/completion/tokens/cost/latency. No `flush()` — Langfuse batches on a background thread, so short-lived clients drop events | all of `agents/` | 🔴 |
| 3 | `anthropic>=0.25` (ancient SDK); model hardcoded as `claude-haiku-4-5-20251001` in two places; a **new** `AsyncAnthropic` client per call; no timeout / retry / thinking / effort / prompt caching | `close_advisor.py:210`, `reflection.py:143` | 🔴 |
| 4 | Forced tool-use with no validation — `dict(block.input)` plus `.get()` with defaults. `confidence` could come back as 5.0 and nothing checks | `close_advisor._ask` | 🟠 |
| 5 | `open_advisor` recycles the close-decision enum: `_DECISION_MAP = {"hold":"open","close":"skip","reduce":"wait"}` — the model emits close-language tokens that mean entry decisions. It has no tracing at all, and its cache never invalidates on a market move | `open_advisor.py` | 🟠 |
| 6 | **Zero tests on any LLM path. No CI whatsoever** (`.github/` does not exist). `ruff`/`mypy` are declared but never run. There are `eslint-disable` comments with no ESLint installed. Postgres/Redis/scheduler — exactly the code that only runs in production — are uncovered | repo-wide | 🔴 |
| 7 | `numpy/scipy/py_vollib/polars/duckdb/pyarrow` are declared in the `quant` extra — **imported in zero places**. The "py_vollib parity test" referenced in two docstrings does not exist | `quant/` | 🟡 |
| 8 | `grid_stats` uses a single flat sigma. No skew, no term structure, no vol path → the condor's put wing is systematically mispriced | `quant/valuation.py:62` | 🟠 |
| 9 | `backtest/runner.py` is a **54-line P&L aggregator** — it takes pre-paired `(candidate, terminal_price)` tuples. It replays nothing, applies no exit rules, and persists nowhere. `scripts/backtest_demo.py` never calls `Pipeline.run_once` → **the "backtest = live parity" claim in ROADMAP is not true in code** | `backtest/`, `scripts/backtest_demo.py` | 🟠 |
| 10 | Enumeration produces **at most 4 condors + 1 DACS per underlying** (2 deltas × 2 wings; DACS returns 0 or 1). No strike / width / DTE sweep. `top_n=10` never binds | `strategies/iron_condor.py:63`, `dacs.py:26` | 🟡 |
| 11 | Unbounded growth: `candidates` is a plain INSERT with no retention (~65k rows/day); the IV-history zset is pulled **entirely** into Python on every scan to compute min/max | `postgres_store.py`, `redis_store.py` | 🟠 |
| 12 | Import bugs: circular import `quant/valuation ↔ strategies/base` (works only because of import order); `quant/__init__.py` shadows the `greeks` module with the `greeks` function | `quant/` | 🟡 |
| 13 | The frontend receives WebSocket messages and **discards the payload** — it re-issues two REST calls instead. No data layer; errors are swallowed by `.catch(() => {})` | `web/src/App.tsx:139` | 🟡 |

---

## 3. What we deliberately do **not** add

The rule: a tool enters only if it solves a problem that actually exists here.

| Tool | Why not |
|---|---|
| **DeepAgents** | A harness for open-ended, long-horizon work with a filesystem, planning tool, and shell. The agents here are short, bounded, and reason over already-computed numbers. Giving an agent a shell is a direct violation of the iron rule. The one capability we wanted from it — letting the model *investigate* — is achieved in Pillar 2 at a fraction of the attack surface |
| **Claude Agent SDK** | Same reasoning. It's a coding/filesystem agent harness, not a decision engine over numbers |
| **Braintrust / LangSmith** | Langfuse is already wired in; v3 brings Datasets + Experiments + Scores — exactly the managed evals platform. One vendor, not two |
| **MCP** | `ARCHITECTURE.md` already rejects it, correctly ("plain typed functions give the same shared code path with less indirection") |
| **Temporal / Prefect** | A 60-second scheduler over 9 symbols. Durable orchestration is complete overkill |
| **Kafka, K8s, CrewAI, AutoGen, full LangChain, external vector DB** | pgvector is right; Redis Streams is enough; ≤3 deployables is a stated project principle |
| **Paid options data** | Not selected in the budget. Pillar 4 works around it with an honest day-by-day backtest that fixes the DACS unfairness even without purchased history |

**LangGraph stays.** It genuinely earns its place: it drives real model nodes through a
conditional revision loop. A single agent wouldn't need a graph.

---

## 4. Pillar 1 — The AI layer, brought to 2026

**Files:** `agents/llm.py` (new), `agents/close_advisor.py`, `agents/open_advisor.py`,
`agents/reflection.py`, `config.py`, `pyproject.toml`, `Dockerfile`.

### 4.1 `agents/llm.py` — the single Anthropic seam

Today `_ask` lives privately inside `close_advisor`, and `open_advisor` imports `_ask`,
`_STANCE_TOOL`, `_DECIDE_TOOL`, `_memory_note` from it — private-name coupling. Extract
into one module:

- **A single module-level client** (lazy singleton) with `timeout=60`, `max_retries=3`.
  Replaces the `AsyncAnthropic(...)` rebuilt on each of the 3 calls in every debate.
- **Structured Outputs** (`output_config={"format": {...}}`) with a Pydantic model instead
  of forced tool-use, **with actual validation**. Fixes finding #4: a `confidence` outside
  [0,1] fails loudly rather than being silently swallowed.
- **Adaptive thinking**: `thinking={"type":"adaptive","display":"summarized"}` combined
  with `output_config={"effort": ...}`. This is a judgment task — thinking is exactly the lever.
- **Prompt caching**: the frozen system prompt and the shared SITUATION block get
  `cache_control`. All three roles share a prefix, so calls 2 and 3 are cache reads —
  which offsets most of the cost of a stronger model.
- **Cost accounting**: read `msg.usage` (including `cache_read_input_tokens` /
  `cache_creation_input_tokens`), aggregate per debate into
  `result["cost"] = {tokens, usd, cache_hit_rate}`, and surface it in the UI. A trading
  system that doesn't know what a decision costs it isn't a flagship system.
- **A typed error chain** — `RateLimitError` → `APIStatusError` → `APIConnectionError`
  instead of `except Exception: pass`. A real failure is logged and returned as
  `engine: "degraded"` with a reason, rather than silently masquerading as
  `deterministic`. **This is a critical distinction**: today an SDK failure looks exactly
  like "no API key".

### 4.2 Tiered models, driven from config

`PAZ_MODEL_ANALYST` / `_CRITIC` / `_DECIDER` / `_REFLECTION` in `config.py`:

| Role | Model | Effort | Rationale |
|---|---|---|---|
| Analyst | `claude-sonnet-5` | medium | Opening argument over given numbers |
| Critic | `claude-sonnet-5` | high | The adversary; drives tools (Pillar 2) |
| **Decider** | **`claude-opus-5`** | high + adaptive thinking | The one call that touches money |
| Reflection | `claude-opus-5` | high | Runs rarely, reasons over all history |

Drop the date suffix from the model id. `AGENT_CONCURRENCY` (present in config, unused)
becomes a real `Semaphore` around the calls.

> **Budget note:** your selections did not include a model upgrade. This structure is
> fully config-driven, so you can keep everything on Haiku/Sonnet and upgrade only the
> Decider — or nothing at all. With prompt caching active, the cost delta is much smaller
> than it looks on paper.

### 4.3 Targeted fixes

- **`open_advisor`** — its own schema (`open | skip | wait`) instead of remapping the
  close enum; a cache signature that invalidates on a market move (like
  `close_advisor._signature`); Langfuse tracing.
- **Cache** — replace the two unbounded global `dict`s with TTL+LRU, backed by Redis when
  `PAZ_PERSIST=redis_postgres` (safe under multi-worker uvicorn; today it breaks).
- **Langfuse v3** — pin `langfuse>=3`, one module-level client,
  `@observe(as_type="generation")` on `ask()` so prompt/completion/tokens/cost/latency are
  actually recorded, and `flush()` on `lifespan` shutdown. Fixes findings #1 and #2.

### 4.4 Stream the debate to the UI

`astream_events` on the LangGraph graph → publish to the existing bus → WebSocket → the
dashboard shows Analyst → Critic → Decider appearing live. Cheap to build, and it
transforms the perceived quality in a demo. Along the way, remove the live `client` from
`DebateState` — that's what currently blocks adding a checkpointer.

---

## 5. Pillar 2 — A deterministic tool belt for the models ⭐

**New file:** `src/paz_rav/agents/tools.py`.

Today the model receives a frozen JSON snapshot and has to guess at "what if". The
upgrade: the quant core is exposed as tools the model **calls**, via the SDK's tool runner.

**This strengthens the iron rule rather than weakening it:** the model still doesn't
compute — it **requests a computation** from `quant/`. Instead of the Critic asserting
"maybe a 3% gap would be dangerous", it runs the scenario and gets a real number back from
the digital twin.

| Tool | Wraps | Returns |
|---|---|---|
| `what_if(spot_move_pct, iv_shift_vol, days_forward)` | `structure_pnl` + `grid_stats` | New P&L, % of max, POP, distance to stop |
| `price_at(spot, on_date)` | `structure_pnl` | Structure value at a point |
| `position_greeks()` | new in `quant/` over `greeks()` | Net delta / gamma / theta / vega |
| `roll_cost(new_expiry, new_short_strike)` | the digital twin | Cost of a roll |
| `similar_cases(k, min_similarity)` | existing `CaseMemory.similar` | Similar closed trades |
| `payoff_curve(n)` | `grid_stats` | The shape, so the model can "see" it |

**The rules that keep this sane:**

1. Every tool is **pure and read-only**, computed in `quant/`. The model chooses *which
   question to ask*, never the answer.
2. `strict: true` schemas with hard bounds (`|spot_move_pct| ≤ 25`, `days_forward ≤ 60`) —
   no wandering.
3. **Every tool call is recorded into `result["evidence"]` and rendered in the UI.** The
   user sees exactly which scenarios the Critic ran and what came back. This is both the
   audit trail and the single strongest demo in the project.
4. `max_uses` per role (Critic 6 probes, Decider 3) — the budget is bounded up front.

**Optional, off by default — catalyst check.** A separate narrow call using Anthropic's
`web_search_20260209` server tool, returning **flags only** in a strict schema
(`earnings_in_days`, `macro_event`, `ex_div`) — never a number that feeds the math. This
is the only honest way to add news awareness without breaking the rule.

---

## 6. Pillar 3 — Evals + CI: prove it works

### 6.1 Golden dataset

`tests/evals/dataset/` — ~60–80 `Situation` / `OpenSituation` cases:

- Every closed position (export script from Postgres) — real cases with a known outcome.
- Hand-built edge cases: short-strike breach, exactly 21 DTE, 90% of max profit, IV crush,
  a gap through the short, and deliberately conflicting signals.

### 6.2 Deterministic graders — *the crown jewel*

For the first time, the iron rule is enforced **mechanically**, not promised:

| Grader | What it checks |
|---|---|
| **`grounding`** | Every number appearing in `reasons` / `rationale` **must** exist in the Situation or in a tool result (numeral extraction + tolerance match). **A fabricated number is a hard fail.** This is exactly what the project promises and has never tested |
| `schema_valid` | Full Pydantic parse |
| `tool_discipline` | Every argument in bounds; no prose contradicting a tool result |
| `stance_opposition` | The Critic genuinely opposes the Analyst (rather than agreeing in other words) |
| `decision_vs_outcome` | Only for cases sourced from real positions: did `close` fire before the profit decayed — **measured against the deterministic exit rule as a baseline**. This produces **a real alpha number for the AI layer** |

Plus `llm-as-judge` (Opus 5) for rationale quality — calibrated against ~20 human-labeled
examples, and used only as a soft metric.

### 6.3 Running it, tests, and CI

- **Langfuse Datasets + Experiments** (v3 `dataset.run()`) — scores land in the same
  project as the production traces. `scripts/eval_run.py` + `pytest -m evals`.
- **LLM-path tests without network**: an `httpx.MockTransport` injected into the client —
  no new dependency, no cassettes. Closes the gap where an LLM-path regression silently
  degrades to the deterministic answer with no test failing.
- **`.github/workflows/ci.yml`** (doesn't exist today): `ruff` + `mypy` + `pytest --cov` +
  `npm run build` + ESLint on every PR, with `services: postgres` (pgvector) to cover, for
  the first time, the repos that only run in production.
- **`.github/workflows/evals.yml`**: runs the golden set and **fails on regression**
  against a stored baseline.
- **`uv` + `uv.lock`**; the `Dockerfile` moves to `uv sync` instead of a hand-written pip
  list — eliminating the drift between `pyproject.toml` and the Dockerfile (two sources of
  truth today).

---

## 7. Pillar 4 — Quant depth

### 7.1 Activate numpy/scipy
Already declared in the `quant` extra, unused. Vectorize `grid_stats` → a 10k-point grid or
50k Monte-Carlo paths in the same wall time. Keep the pure-Python path as the reference and
add a **parity test between the two, plus against `py_vollib`** — the one promised in two
docstrings and never written.

### 7.2 Volatility surface
New `quant/surface.py`: fit **SVI per expiry** (or SSVI across expiries) with no-arbitrage
checks. Replaces the single flat sigma with `iv(strike, expiry)` inside `grid_stats`,
`scoring.finalize`, and `exit_rules`.

**This changes real numbers** — the condor's put wing is priced correctly for the first
time. In the UI: a smile chart plus term structure (the visual that sells the project).

### 7.3 Fat tails
Alongside the lognormal, a **bootstrapped-historical / Student-t** distribution for the POP
integral. Show `pop_lognormal` next to `pop_empirical` — honest, and visibly differentiating.

### 7.4 Portfolio risk
New `positions/portfolio.py`: net delta / gamma / theta / vega across the whole book,
concentration by underlying, and a correlated stress test ("SPX ‎-5% with IV ‎+10 — what
happens to the book?"). Fed into the Reflection agent and a new KPI row.

**This is precisely the trigger `ARCHITECTURE.md` names as justifying another agent**
("they'd only earn their place managing a correlated portfolio") — so the expansion aligns
with the author's stated intent rather than working against it.

### 7.5 An honest backtest
`backtest/walk_forward.py` replaces `scripts/backtest_demo.py`:

1. Iterate **day by day** over a price path.
2. **Apply the real exit rules** each day via `exit_manager.sweep`.
3. Optionally route the close decision through the AI debate, to measure **AI vs. rules**.

This is literally the fix `ROADMAP.md` asks for in order to judge DACS fairly ("A fair
backtest needs a day-by-day price path with those exit rules modeled"). `BacktestResult`
persists to Postgres, plus an endpoint and an equity-curve chart.

### 7.6 Search space
Finding #10: widen enumeration into a real sweep (short delta × wing width × DTE), now
that scoring is vectorized. From a system that proposes 5 structures to an optimizer with
an efficient-frontier view. Along the way, fix the fact that `regime_fit` (range ×0.36–×1.56)
currently dominates the expectancy term itself.

### 7.7 Correctness fixes riding along
- Circular import `quant/valuation ↔ strategies/base`; the `greeks` module shadowing in
  `quant/__init__.py`.
- `backtest/payoff.pnl_at_expiry` is wrong for multi-expiry structures (DACS) — route to
  `structure_pnl`.
- Retention + a partial index on `candidates`; sample IV history once per day and cache
  min/max.
- `LOG_LEVEL` is never actually applied — real structured logging.
- Dead code: `quant/pop.prob_of_profit`, `analytics/iv.iv_percentile`.

---

## 8. Execution order

| Stage | Deliverable | Why in this order |
|---|---|---|
| **0** | `uv.lock` + green CI + Langfuse v3 fix | Without measurement, no improvement can be proven |
| **1** | Pillar 1 — `agents/llm.py`, tiered models, caching, cost tracking | Foundation for everything else |
| **2** | Pillar 2 — the tool belt + `evidence` in the UI | The feature that creates the "wow" |
| **3** | Pillar 3 — golden set + graders + evals in CI | Proves 1 and 2 actually improved things |
| **4** | Pillar 4 — surface, MC, portfolio, honest backtest | What makes it trustworthy with real money |

---

## 9. End-to-end verification

```bash
# core
uv sync --extra quant --extra agents --extra feeds --extra dev
uv run ruff check . && uv run mypy src && uv run pytest --cov=paz_rav
cd web && npm run build          # tsc -b must pass (noUnusedLocals is on)

# full stack
docker compose up -d --build
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/api/top?n=5"
docker inspect --format='{{.State.Health.Status}}' paz-rav-app-1   # → healthy
```

**Pillar 1** — with a real `ANTHROPIC_API_KEY`: `POST /api/positions/{id}/close-advice`,
then confirm in the Langfuse UI that there is a **generation** with prompt / completion /
tokens / cost (not just an event), and that `cache_read_input_tokens` is greater than zero
on calls 2–3. Confirm `result.cost` renders in the UI. Without a key, the deterministic
path still answers and all 106 existing tests pass.

**Pillar 2** — open a position and request advice: `result["evidence"]` must contain
`what_if` calls with in-bounds arguments, and the returned P&L must be **identical** to a
manual `structure_pnl` computation with the same parameters (parity test).

**Pillar 3** — `uv run python scripts/eval_run.py` → the run appears in Langfuse
Experiments; `grounding` = 100%; a CI run on a PR with a deliberately bad prompt must
**fail**.

**Pillar 4** — `pytest tests/test_surface.py` (arbitrage-free SVI, parity against the pure
grid); `uv run python -m paz_rav.backtest.walk_forward` — DACS must be evaluated **with**
exit rules, and report a different number from the current passive simulation.
