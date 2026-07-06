# Paz Rav — Real-Time Options Strategy Engine

> Finds the **right options strategy, at the right time, for the right duration** —
> and proves the edge in backtest before a dollar is risked. A deterministic quant core
> does all the math; a lean two-agent AI layer adds judgment and a full audit trail on
> top. Nothing on screen is guessed.

## What it does

A trader's real problem is three decisions, made continuously and without emotion:

- **Which structure** — Iron Condor vs. DACS 1.0 (a diagonal calendar spread)
- **When to enter** — only when the edge is actually present (IV rank, regime, RSI)
- **How long to hold** — take profit early, time-stop, or cut a tested side

Humans do all three badly: they hold losers, cut winners, and sell into the wrong
regime. Paz Rav scans a fixed universe of underlyings, ranks candidates deterministically,
runs each one past an AI committee (Analyst proposes, Critic argues against), and serves
a live dashboard where you open paper positions and get told exactly when to close them.

**The one rule that matters:** every greek, IV, price, POP, and P&L comes from
deterministic Python. The AI never computes a number — it only reasons over numbers the
quant core already produced. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for why.

## Quick start

```bash
docker compose up -d --build
# → open http://localhost:8000
```

One command, the whole stack (Postgres + Redis + the engine + dashboard). Runs on
offline demo data by default; set `PAZ_DATA=yfinance` for live delayed quotes. Full
options (running from source, real persistence, cloud deployment) are in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Status

| Phase | What | State |
|---|---|---|
| 1 | Deterministic core + live dashboard | ✅ done |
| 2 | Two-agent AI judgment (Analyst + Critic, LangGraph, Langfuse) | ✅ done |
| 3 | Position lifecycle + advisory exit alerts | ✅ done |
| 4 | Real broker connection, hardening | ⏳ not started |

Details, what's proven vs. what's a known gap, and backtest results:
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Learn more

- [**`docs/ARCHITECTURE.md`**](docs/ARCHITECTURE.md) — the pipeline, why two agents (not
  zero, not seven), the tech stack with honest trade-offs, repo layout.
- [**`docs/DEPLOYMENT.md`**](docs/DEPLOYMENT.md) — running it (Docker or from source),
  real persistence, cloud deployment stages.
- [**`docs/ROADMAP.md`**](docs/ROADMAP.md) — phase-by-phase status and how we verify it
  actually works.
- [**`CLAUDE.md`**](CLAUDE.md) — commands and architecture notes for AI coding agents
  working in this repo.
