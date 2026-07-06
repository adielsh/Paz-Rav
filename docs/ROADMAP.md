# Roadmap & Verification

## Phase status

**Phase 1 — Deterministic core + live dashboard.** ✅ Done.
Feeds (yfinance/IBKR), analytics (IV rank, regime, RSI), builder (delta-based Iron
Condor + DACS), storage (Redis/Postgres), the wired pipeline + scheduler + bus,
backtester, FastAPI + WebSocket API, and a live React dashboard (ranked candidates,
payoff inspector) — verified running on real data.

**Phase 2 — Two-agent AI judgment.** ✅ Done.
Analyst + Critic via a real LangGraph loop (a severe Critic objection sends a "take"
back to the Analyst, who downgrades it), traced in Langfuse, explanations via Claude.
All three verified live against real API keys.

**Phase 3 — Position lifecycle + learning loop.** ✅ Done.
- `Position` domain object (a candidate that was actually opened), with a dashboard
  panel and `POST /api/positions/open/{u}/{idx}` + `GET /api/positions`.
- Exit Manager: deterministic per-strategy rules (condor: 50%-profit-target / 21-DTE
  time-stop / short-strike breach; DACS: stop at short_strike+offset / ~3x-debit
  profit-target / 2-weeks-before-expiry) — **advisory only**, never auto-closes, since
  the real fill happens at your broker.
- Closing a position is a deliberate user action recording the real net price; the
  realized P&L scores back onto the exact Langfuse trace the opening decision produced.
- Both candidates and positions persist to Postgres (`PAZ_PERSIST=redis_postgres`),
  verified to survive a container restart.

**Not yet built:**
- Case-memory (RAG-lite retrieval over past setups) — deferred on purpose, since there
  isn't yet a real body of outcomes to retrieve against.
- A real IBKR connection (`adapters/ibkr.py` is stubbed but not wired) — not needed
  until either manual order placement or the Exit Manager needs true real-time watching;
  yfinance's delayed data is sufficient for an advisory-only system.
- Cloud deployment (Terraform scaffold exists, nothing applied).

## How we know it works

1. **Deterministic parity** — greeks / IV within tolerance vs. a vendor snapshot.
2. **Backtest = live parity** — the same history replayed live yields the same signals,
   because both paths call the same `Pipeline.run_once()`.
3. **Walk-forward backtest.** `PYTHONPATH=src python scripts/backtest_demo.py` runs a
   walk-forward simulation. Real historical option chains aren't freely available, so it
   simulates chains from Black-Scholes over a random-walk underlying whose *realized*
   vol is intentionally lower than the *implied* vol it's priced at — the same
   volatility risk premium condor sellers harvest live.
   - **Iron Condor: 92.5% win rate, +2.33 avg P&L, positive total across 40 simulated
     trades** — the edge shows up exactly where the thesis predicts.
   - **DACS: currently negative in this simulation** — an honest finding, not a bug. The
     script holds positions passively to expiry with no stop-loss or early exit, but
     DACS's real edge is in *active* management (cut losers early, take profit early).
     A fair DACS backtest needs a day-by-day price path with those exit rules modeled —
     that's a concrete next step, not evidence the strategy doesn't work.
4. **Trace audit** — every recommendation shows every number and the Critic's objection;
   zero un-sourced figures.
5. **Paper forward-test** — position P&L vs. a mechanical baseline, scored onto the
   Langfuse traces that produced each decision.
