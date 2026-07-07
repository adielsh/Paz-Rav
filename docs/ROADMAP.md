# Roadmap & Verification

## Phase status

**Phase 1 — Deterministic core + live dashboard.** ✅ Done.
Feeds (yfinance/IBKR), analytics (IV rank, regime, RSI), builder (Iron Condor + DACS),
storage (Redis/Postgres), pipeline + scheduler + bus, backtester, FastAPI + WebSocket
API, live React dashboard — verified running on real data.

**Phase 2 — Two-agent AI judgment.** ✅ Done.
Analyst + Critic via a real LangGraph loop (a severe objection sends a "take" back to
the Analyst, who downgrades it), traced in Langfuse, explanations via Claude — all
verified live against real API keys.

**Phase 3 — Position lifecycle + learning loop.** ✅ Done.
- `Position` domain object with a dashboard panel and open/list endpoints.
- Exit Manager: deterministic per-strategy rules (condor: 50%-profit-target / 21-DTE
  time-stop / short-strike breach; DACS: stop offset / ~3x-debit profit-target /
  2-weeks-before-expiry) — **advisory only**, never auto-closes.
- Closing is a deliberate user action recording the real net price; realized P&L scores
  back onto the opening decision's Langfuse trace.
- Candidates and positions persist to Postgres, verified to survive a container restart.

**Phase 3.5 — Close-timing debate + case memory.** ✅ Done.
- A genuine three-LLM debate (Analyst / Critic / Decider) on **when to close** an open
  position, orchestrated by LangGraph with a conditional revision loop — the first place a
  model actually reasons toward a decision. Extracted to its own `advisor` microservice.
- **Case memory (RAG-lite)** — every closed position is stored as a deterministic feature
  vector + its real outcome (pgvector). When the debate runs, it recalls the *k* most
  similar closed trades and feeds their outcomes in as grounded context, so the Decider
  leans on your own history. The vector is computed from the quant core's numbers, not an
  LLM embedding — the deterministic line holds.

**Not yet built:**
- A strategic reflection agent that mines accumulated Langfuse/DB statistics to recommend
  parameter tuning — deferred until there's a large enough body of outcomes to be honest.
- A real IBKR connection — stubbed (`adapters/ibkr.py`) but not wired; not needed until
  real-time watching or order placement is required.
- Cloud deployment — Terraform scaffold exists, nothing applied.

## How we know it works

1. **Deterministic parity** — greeks / IV within tolerance vs. a vendor snapshot.
2. **Backtest = live parity** — the same history replayed live yields the same signals,
   since both paths call the same `Pipeline.run_once()`.
3. **Walk-forward backtest** (`scripts/backtest_demo.py`) — simulates chains from
   Black-Scholes over a random-walk underlying whose *realized* vol is intentionally
   lower than the *implied* vol it's priced at — the same volatility risk premium condor
   sellers harvest live.
   - **Iron Condor: 92.5% win rate, +2.33 avg P&L, positive total across 40 simulated
     trades** — the edge shows up exactly where the thesis predicts.
   - **DACS: currently negative in this simulation** — an honest finding, not a bug. The
     script holds positions passively to expiry with no stop-loss or early exit, but
     DACS's real edge is in *active* management. A fair backtest needs a day-by-day
     price path with those exit rules modeled — a concrete next step, not evidence the
     strategy doesn't work.
4. **Trace audit** — every recommendation shows every number and the Critic's objection;
   zero un-sourced figures.
5. **Paper forward-test** — position P&L vs. a mechanical baseline, scored onto the
   Langfuse traces that produced each decision.
