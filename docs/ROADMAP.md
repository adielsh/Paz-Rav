# Roadmap — what's done, and what we actually know

Two questions, kept separate on purpose: **is it built?** and **does it work?** A lot of
software confuses the two. This page doesn't.

## Built

**Phase 1 — deterministic core + live dashboard.** ✅
Feeds (yfinance / IBKR stub), analytics (IV rank, regime, RSI), builder (Iron Condor +
DACS), storage (Redis / Postgres), pipeline + scheduler + bus, backtester, FastAPI +
WebSocket, React dashboard. Verified running on real data.

**Phase 2 — the deterministic committee.** ✅
Analyst + Critic in a real LangGraph loop — a severe objection sends a "take" back for one
revision. No LLM call, so it runs on every candidate for free.

**Phase 3 — position lifecycle.** ✅
`Position` as a first-class object with a dashboard panel. Per-strategy exit rules (condor:
50% profit target / 21-DTE time stop / short-strike breach; DACS: stop offset / ~3× debit
target / two weeks before expiry) — **advisory only**, never auto-closing. Closing is a
deliberate user action recording the real net price. Candidates and positions survive a
container restart.

**Phase 3.5 — the LLM debates + case memory.** ✅
Three real Claude calls (Analyst / Critic / Decider) on when to close — and, via
`open_advisor`, on when to open. Extracted to its own `advisor` container. Every closed
position is stored as a deterministic feature vector plus its real outcome (pgvector), so the
debate can recall how similar trades ended.

**Phase 3.6 — the reflection pass.** ✅
Reads aggregate stats over all closed trades and suggests what to tune. Python computes every
statistic; the model only interprets. Gated by a minimum sample size, and it remembers its own
past reflections.

**Phase 4 — a real broker, hardening.** ⏳ Not started.

## What we actually know

This is the part worth being strict about.

### ✅ Solid

- **106 tests pass**, with no infrastructure and no network. The quant core, strategies,
  stores, agents and API all have coverage.
- **Backtest/live parity is structural, not claimed** — both paths call the same
  `Pipeline.run_once()`, so they cannot drift.
- **Zero un-sourced numbers.** Every figure on screen traces back to a Python computation;
  forced tool-use means a model can't emit one of its own.
- **The engine produces sane candidates on real chains** — verifiable in one command with
  `scripts/pipeline_demo.py SPY`.

### ⚠️ Proven only against itself

`scripts/backtest_demo.py` reports **Iron Condor: 92.5% win rate, +2.33 avg, +93.10 total
over 40 trades.** Read that number carefully before believing it.

The backtest builds synthetic chains from Black-Scholes over a random walk whose *realized*
vol is deliberately set below the *implied* vol it's priced at. That is the volatility risk
premium condor sellers harvest — but hard-coding it into the simulation means a
premium-selling strategy has to win. **The result confirms the code implements the thesis; it
does not confirm the thesis.**

What would actually be evidence: replaying real historical option chains, with real bid/ask
spreads and real fills.

### ⚠️ The most consequential number in the system is an assumption

`Settings.vrp` defaults to **0.15**, and `scoring.finalize()` computes
`realized = sigma * (1 - vrp)`. This is **not backtest-only** — `api/app.py` passes
`settings.vrp` straight into the live `BuildConfig`.

So every POP, every `expected_pnl`, and the ranking `score` itself are computed on the
assumption that the market's implied vol is 15% higher than what will actually realize. If
that premium is smaller than 15% for a given name or period — or negative, as it is around
event risk — the dashboard is systematically optimistic, and the ranking prefers whatever is
most exposed to the assumption.

The premium is real and well documented, so 0.15 is a defensible default, not a bug. But it
should be understood as *the trader's thesis expressed as a config value*, not as something
the system measured. Measuring it per-underlying from IV history — which the project already
stores — would turn the single largest assumption into an observation.

### ❌ Known negatives and gaps

- **DACS backtests negative** (8 trades, 12.5% win rate, −5.88 total). Honest caveat: the
  script holds it passively to expiry with no stop and no early profit-take, and DACS's edge
  is meant to come from *active* management. A fair test needs a day-by-day price path with
  the exit rules modelled. Until that exists, half the product is unvalidated.
- **Langfuse records markers, not traces.** Each decision writes a small `create_event` with
  metadata — but the actual Claude calls aren't wrapped as generations, so prompts, outputs,
  token counts, latency and cost are not captured. "Full audit trail" is currently an
  overstatement; the plumbing exists, the payload doesn't.
- **Case memory and reflection are worth ~nothing yet.** Both are correct, tested code that
  needs dozens of closed trades before it says anything useful. Right now they're architecture
  waiting for data.
- **No real IBKR connection.** `adapters/ibkr.py` is a stub. Not needed until real-time
  quotes or order placement are.
- **Nothing deployed.** A Terraform scaffold exists at `infra/terraform/`; it has never been
  applied.

## Next, in order of what would actually move the needle

1. **A real-chain backtest** — the single change that would turn "the code works" into "the
   strategy works".
2. **Measure `vrp` from stored IV history instead of hard-coding 0.15**, so the biggest
   assumption in the ranking becomes a measurement.
3. **Day-by-day DACS backtest with exit rules modelled**, so the negative result is either
   fixed or confirmed.
4. **Wrap the LLM calls as Langfuse generations**, so the audit trail is real and cost is
   visible.
5. Paper forward-testing against a mechanical baseline — the only thing that eventually
   validates the AI layer's judgment rather than its plumbing.
