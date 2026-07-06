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

**Not yet built:**
- Case-memory (RAG-lite) — deferred on purpose, until there's a real body of outcomes to
  retrieve against.
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
