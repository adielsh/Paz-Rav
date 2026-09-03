# SPX Adaptive Iron Condor

An automated SPX (SPXW, PM-settled) iron-condor trading platform on the Interactive Brokers API.

A deterministic trading daemon plus separate services for the API, web console, database and
centralized logging. **Fully mechanical — no AI, no ML, no black boxes.** Every decision is a
rule you can read in the source and an audit row in Postgres.

> **Paper trading by default.** Three independent locks must all be released before a single
> order reaches the broker. See [Safety](#safety).

---

## Contents
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Safety](#safety)
- [Quick start](#quick-start)
- [The web console](#the-web-console)
- [Configuration](#configuration)
- [How P&L is calculated](#how-pl-is-calculated)
- [Market data](#market-data)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Known limitations](#known-limitations)

---

## What it does

Once per trading day at **14:30 ET** the daemon:

1. Reads the **VIX 5-minute average** and picks a delta regime
   — `VIX < 14` → 0.15/0.15 · `14–22` → 0.30/0.20 (put-skewed) · `> 22` → **suspend**.
2. Selects the SPXW expiry nearest **40 DTE** (35–45 window).
3. Picks short strikes by **delta**, then long wings 50 points out, with a **zero-bid guard**
   that walks the wing inward if it has no bid.
4. Runs five **pre-flight gates**: minimum credit, liquidity spread, pyramiding/overlap,
   `whatIf` margin against a budget, and a halt check.
5. Either **proposes the trade for your approval** (default) or places it directly.

Open positions are managed automatically: a resting **GTC take-profit** at credit − $0.50, and
a **25-DTE gamma stop** that force-closes with a limit walk.

Every gate decision — pass or reject — is persisted with its inputs, so you can always answer
"why didn't it trade today?".

---

## Architecture

```
                    ┌──────────────┐
                    │  ib-gateway  │  IBKR paper gateway (IBC auto-login)
                    └──────┬───────┘
                           │ TWS API
          ┌────────────────┼────────────────┐
          │                                 │
   ┌──────▼───────┐                  ┌──────▼──────┐
   │ trading-core │                  │     api     │  read-only IB bridge
   │  THE DAEMON  │                  │  (FastAPI)  │  + Flex statements
   │ only service │                  └──────┬──────┘  + kill switch
   │ that trades  │                         │
   └──────┬───────┘                         │
          │          ┌──────────┐           │
          └─────────►│ postgres │◄──────────┘
                     └──────────┘
                           ▲
                    ┌──────┴───────┐
                    │   frontend   │  React + Redux + AG Grid
                    └──────────────┘
```

| Service | Container | Port | Role |
|---|---|---|---|
| `ib-gateway` | `ibgw-paper` | 4002, 5900 (VNC) | Headless IBKR gateway, IBC auto-login |
| `trading-core` | `condor-core` | — | The daemon. **Only service that can place orders** |
| `postgres` | `condor-db` | 5432 | Trades, fills, gate decisions, P&L, proposals, control |
| `api` | `condor-api` | 8000 | Reporting API + read-only IB bridge + approvals + kill switch |
| `frontend` | `condor-frontend` | **8080** | Web console |
| `loki`/`promtail`/`grafana` | `condor-*` | 3000 | Structured log aggregation |

**The API cannot trade.** It only reads the database and flips status columns. The daemon owns
the broker connection and re-validates everything before transmitting. That separation is
deliberate: a bug in the web layer can never move money.

---

## Safety

Three independent locks, all of which must be released:

### 1. `PLACE_ORDERS` (default `0`)
Dry-run. Gates are evaluated and every decision is persisted, but **no order is transmitted**.

### 2. `REQUIRE_APPROVAL` (default `1`)
A condor that passes every gate is **not** sent. It is written to `trade_proposals` and
surfaced in the console, where you approve or reject it.

On approval the daemon **re-prices and re-validates** before transmitting — the quote behind a
proposal is minutes old, so it re-checks the minimum credit, the kill switch, and runs a fresh
`whatIf` margin check **for the quantity you approved**. A stale quote can never be traded.

### 3. Paper-account guard
`trading-core` refuses to start unless the connected account starts with `DU`
(`PAPER_ACCOUNT_PREFIX`).

Plus a **kill switch** (`control.trading_enabled`) polled before every entry, flippable from the
console header.

> ⚠️ **Exits are automatic.** The approval gate covers *entries only*. Once a position is open,
> the GTC take-profit and the 25-DTE gamma stop act without asking — by design; you don't want a
> stop waiting on a click.

---

## Quick start

**Requirements:** Docker + Docker Compose, an IBKR **paper** account.

```bash
git clone https://github.com/<you>/spx-adaptive-iron-condor.git
cd spx-adaptive-iron-condor

cp .env.example .env      # then edit — see Configuration below
docker compose up -d
docker compose logs -f trading-core
```

Open **http://127.0.0.1:8080**.

The daemon starts in dry-run with approvals on, so nothing can trade until you deliberately
change that.

---

## The web console

Bilingual (English / עברית, full RTL), light and dark themes, at `127.0.0.1:8080`.

| Page | What it shows |
|---|---|
| **Overview** | Open positions, realized P&L, equity curve, margin headroom |
| **Performance** | Real account from IBKR Flex statements — the analytical centre |
| **Entry approvals** | Pending proposals awaiting your decision |
| **Strategy analytics** | Win rate, profit factor, expectancy, drawdown, distributions |
| **Paper account** | Live positions, executions and orders straight from the gateway |
| **Bot positions / trades / Gate decisions** | The daemon's own durable audit log |

**Entry approvals** shows each proposal as a decision card: a strike ladder with the profit zone
drawn between the shorts, what you collect and what you risk in dollars, a copies stepper, and
one button. Changing copies rescales the figures live.

Every grid is AG Grid: sortable, per-column filters, full-text search, CSV export, resizable
columns. Date columns sort chronologically, not lexicographically. Rows are tinted by outcome
and expand inline to show the individual option legs.

### Accounts and what each one can see

Every row the console serves is filtered by the signed-in account. `trades`, `gate_decisions`,
`trade_proposals`, `control` and `nav_snapshots` carry a `user_id`; `pnl` and `fills` are scoped
through their parent trade. A second account sees zero trades, zero gate decisions and zero P&L,
and `POST /proposals/{id}/approve` on a condor it does not own returns 404 — the same answer as
a proposal that does not exist, so the id itself leaks nothing.

Approving is the write that matters here: it is what eventually puts money to work. The
authorisation check is the `user_id` predicate in the `UPDATE` itself rather than a separate
lookup, so there is no window between checking and writing.

**The broker connection is the owner's, and says so.** `ib_bridge` holds one IB client against
one gateway and one account, so `/ib/*` is not per-user data and no `WHERE` clause could make it
so. Those routes return **403** to anyone but the owner instead of quietly showing them someone
else's positions. The same applies to the kill switch: `GET /control` returns
`available: false` for an account with no daemon, and the console hides the control rather than
offering a switch that toggles nothing. This is the boundary that lifts when a second broker
connection exists — it is not a placeholder to be patched with a filter.

Rows written before isolation existed are backfilled to the owner account on first boot, since
one broker connection produced all of them. A row left unclaimed is visible to nobody, which is
the safe direction to fail.

### Ask about the data

A bot button in the corner of every page opens a chat about whatever is on screen — "how much
has the real account actually made", "which underlyings do I trade most", "why hasn't the bot
opened a position".

It is grounded, not chatty. The server builds a snapshot of your account — counts, totals,
per-underlying and per-month aggregates, the NAV curve's extremes, the most recent fills — all
computed in Python from Postgres and the cached Flex statement, then hands it to Claude with one
standing instruction: **never produce a number that is not already in the snapshot.** Ask for a
figure the snapshot doesn't hold and it says so instead of estimating. That keeps the project's
core rule intact — the model reads numbers, it never calculates them.

It also has to name its source. Seeded demo rows, the real IBKR statement, and the paper gateway
are three separate blocks in the snapshot, each flagged, and the model is told never to blend
them into one figure.

Set `ANTHROPIC_API_KEY` in `.env` and restart the `api` service to switch it on; leave it blank
and the widget says it is off. The assistant is read-only — it cannot open, approve or close
anything, and the API it talks to has no route that could.

**Why it costs what it costs.** The snapshot is ~6,500 tokens and dominates the bill, so it is
sent as a *cached* prompt prefix: the first question in a five-minute window writes the cache,
every question after it re-reads the same bytes at a tenth of the price. That is also why
`build_snapshot()` contains no timestamp — a clock reading in the prefix would change the bytes
on every call and silently defeat the cache. Watch `usage.cache_read` in the response: if it
stays zero across repeated questions, something made the prefix unstable.

For the same reason `CHAT_EFFORT` defaults to `low`. Measured on the two questions that matter —
keeping the real account apart from the seeded demo, and refusing to invent a win rate — low
effort produced the same answers as the default in half the wall time. Looking a figure up in a
JSON blob is not a reasoning problem.

### Forgotten password

There is no mail server in this stack, so the reset link is **written to the API log** instead
of emailed. That is a deliberate trade: on a console bound to localhost, whoever can read the
server's logs is already the person who owns the machine.

1. On the sign-in screen, click **Forgot your password?** and enter the address.
2. Read the link off the server:

```bash
docker compose logs api | grep "PASSWORD RESET LINK"
# PASSWORD RESET LINK for you@example.com (valid 30 minutes, single use):
#   http://127.0.0.1:8080/?reset=<token>
```

3. Open it. The console asks for a new password and signs you in.

The link is **single use** and expires after `RESET_TTL_MINUTES` (default 30). Only its SHA-256
is stored, so a database dump yields no working link. `/auth/forgot` answers identically whether
or not the address is registered, and refuses to mint a second live token within 60 seconds.
Changing your password from **Settings** kills any reset link still outstanding.

> Note: Promtail ships container logs to Loki, so a reset link is also visible in Grafana on
> `:3000` for its lifetime. Both ports are bound to localhost; treat access to either as
> equivalent to account access.

---

## Configuration

All settings live in `.env` (git-ignored — **never commit it**). Copy `.env.example` to start.

### Credentials
| Variable | Purpose |
|---|---|
| `TWS_USERID` / `TWS_PASSWORD` | IBKR **paper** login |
| `VNC_SERVER_PASSWORD` | Optional — watch the gateway UI on :5900 |
| `FLEX_TOKEN` / `FLEX_QUERY_ID` | IBKR Flex Web Service, for real statement data |

To get Flex credentials: *Account Management → Reporting → Flex Web Service* (enable, copy the
token), then create an **Activity Flex Query** including **Trades** and **Change in NAV**, period
"Last 365 Calendar Days", and copy its Query ID.

### Console accounts
| Variable | Default | Purpose |
|---|---|---|
| `APP_SECRET_KEY` | — (required) | Signs sessions and encrypts stored broker credentials |
| `ALLOW_SIGNUP` | `1` | `0` closes registration (the first account can always be created) |
| `SESSION_HOURS` | `12` | Session lifetime |
| `COOKIE_SECURE` | `0` | Set to `1` once the console is served over HTTPS |
| `CONSOLE_URL` | `http://127.0.0.1:8080` | Base URL used to build the password-reset link |
| `RESET_TTL_MINUTES` | `30` | How long a reset link stays usable (single use regardless) |

### Assistant
| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables the in-console assistant. Blank = widget disabled |
| `ANTHROPIC_WORKSPACE_ID` | — | Required only for an identity-linked key, which is rejected without it |
| `CHAT_MODEL` | `claude-opus-5` | Model used for the assistant |

### Order safety
| Variable | Default | Meaning |
|---|---|---|
| `PLACE_ORDERS` | `0` | `1` allows orders to reach the broker |
| `REQUIRE_APPROVAL` | `1` | `0` gives the bot fully automatic entry |
| `PROPOSAL_TTL_MINUTES` | `120` | How long a pending proposal stays actionable |
| `MAX_APPROVAL_LOTS` | `20` | Upper bound on approved size |
| `MARKET_DATA_TYPE` | `3` | `1` live · `3` delayed (see below) |
| `PAPER_ACCOUNT_PREFIX` | `DU` | Clear only for a deliberate go-live |

Strategy parameters (deltas, DTE window, wing width, gates, TP delta) are explicit constants in
`trading-core/app/config.py` — auditable rather than tunable at runtime.

---

## How P&L is calculated

Two rules that the platform holds to, because both were bugs worth fixing:

**P&L is per position, never per leg.** A four-leg condor nets to one number. Reading individual
legs is meaningless — one leg of a January SPX spread showed `+$72,840` while the position it
belonged to actually netted `−$2,129`.

**P&L is attributed to the close date.** A trade opened on the 20th and closed on the 27th
belongs to the 27th, because that is when the money was booked. This is how IBKR reports it, and
the console reconciles against the broker exactly:

```
27 Jul 2026    by open date:   $125      ← wrong
               by close date:  $474      ← matches IBKR
```

**Returns are time-weighted and deposit-adjusted.** Period return is computed from IBKR's daily
NAV blocks by compounding each day's gain over the capital actually at work that day, so a
mid-period deposit is never counted as performance. Over the full statement the naive
`(end − start) / start` gives −474,054 % (NAV opened at $5.36); the correct figure is **−42.6 %**.

---

## Market data

The strategy needs SPX index and option quotes **with greeks** — delta drives strike selection.

If your account has no live SPX subscription, set `MARKET_DATA_TYPE=3` (the default) to use
delayed data. The full pipeline runs, but quotes lag ~15 minutes:

> Delayed quotes are fine for validating the pipeline. They are **not** execution-grade
> pricing. The daemon logs a warning at startup whenever it is not on live data.

For real trading, subscribe to SPX market data in Account Management and set
`MARKET_DATA_TYPE=1`.

---

## Testing

```bash
cd trading-core && python -m pytest tests/ -q
```

Covers the pure logic: delta regime selection, DTE windows, tick rounding, expiry maths.

### Validating the order sign convention
`trading-core/app/verify_sign.py` is a **read-only** probe. It builds a real condor from live
data and asks IBKR to price both order formulations via `whatIfOrderAsync`, which returns a
margin projection **without transmitting anything**:

```bash
docker exec condor-core python -m app.verify_sign
```

The convention (`BUY` at a **negative** limit opens for a credit) is confirmed: IBKR returns a
maintenance-margin change equal to the wing width × 100 and a **positive** equity change, while
the opposite formulation is rejected outright with *"Riskless combination orders are not
allowed"*.

---

## Project layout

```
trading-core/app/
  main.py           daemon loop, entry flow, proposals, state recovery
  data_fetcher.py   IB read layer: chain, greeks, quotes, halt guards
  risk_manager.py   the five pre-flight gates
  execution.py      combo orders, limit walks, GTC take-profit
  config.py         all strategy parameters
  db.py             SQLAlchemy models
  verify_sign.py    read-only sign-convention probe

api/app/
  main.py           reporting API, approvals, kill switch
  ib_bridge.py      read-only live IB bridge
  flex.py           IBKR Flex statement ingest + cache

frontend/src/
  pages/            Overview, RealAccount, Proposals, Analytics, …
  components/       DataGrid (AG Grid), DateRangePicker, ui kit
  store/            RTK Query + Redux slices
  i18n/             English / Hebrew

observability/      loki, promtail, grafana provisioning
examine.py          original end-to-end reference script
```

---

## Known limitations

- **Exits are not gated by approval** — the take-profit and gamma stop act autonomously.
- **Delayed market data by default.** Live data needs an SPX subscription.
- **One entry per day**, fixed lot size unless you approve more copies.
- **The Flex statement lags.** Same-day trades appear after IBKR generates the statement; the
  live gateway bridge (`/ib/*`) covers the current session.
- IBKR permits **one market-data session per login**. Another logged-in TWS, mobile app, or web
  session will starve the gateway and quotes will return empty.

---

## License

Private project. Not investment advice. Options trading carries substantial risk of loss —
you are responsible for anything this software does with your account.
