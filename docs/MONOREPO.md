# The monorepo

Two projects that were separate repos until they weren't. This page is the map.

## Why they merged

Each was the other's missing half.

- **The engine** (`src/paz_rav/`) ranks Iron Condor and DACS candidates across a universe of
  underlyings, with a deterministic quant core and an AI judgment layer — and had no way to
  reach a broker. `adapters/ibkr.py` is still a 54-line stub.
- **The console** (`apps/console/`) has a working IBKR connection, real order execution with
  a human approval gate, real account reporting, multi-user accounts, and a UI worth
  keeping — driving exactly one hard-coded strategy on one symbol.

They already shared a language, a web framework, a database and a broker library. Keeping
them apart meant maintaining two of everything to connect two halves of one idea.

## What runs where

```
docker compose up -d --build          # from the repo root. That's it.
```

| URL | What |
|---|---|
| **http://127.0.0.1:8080** | **The console. Start here.** |
| http://127.0.0.1:8010 | The engine's own dashboard (pre-merge UI, pending migration) |
| http://127.0.0.1:8000 | The console's API |
| http://127.0.0.1:8001 | The engine's AI advisor service |
| http://127.0.0.1:3000 | Grafana (admin/admin) — container logs via Loki |
| http://127.0.0.1:8081 | The legacy lean dashboard, kept as a fallback |

Every port binds to `127.0.0.1`. Nothing is exposed to the network.

| Service | Container | Trades? |
|---|---|---|
| `trading-core` | `condor-core` | **Yes — the only one that can.** |
| `api` | `condor-api` | No. Reads the DB, flips status columns, proxies read-only views |
| `frontend` | `condor-frontend` | No |
| `engine` | `condor-engine` | No. Advisory only — no broker connection, no order route |
| `advisor` | `condor-advisor` | No |
| `ib-gateway` | `ibgw-paper` | It *is* the broker connection |
| `postgres` / `redis` | `condor-db` / `condor-redis` | — |
| `loki` / `promtail` / `grafana` | `condor-*` | — |

## One database, two schemas

Both halves use the **`condor`** database on one `pgvector/pgvector:pg16` container.

| Schema | Owner role | Tables |
|---|---|---|
| `public` | `condor` | `users`, `trades`, `fills`, `gate_decisions`, `pnl`, `trade_proposals`, `control`, `flex_cache_user`, `nav_snapshots`, `password_resets`, `user_credentials` |
| `engine` | `paz` | `candidates`, `positions`, `case_memory`, `reflections` |

The split needs **no code change on either side**. The engine's asyncpg repositories all
issue an unqualified `CREATE TABLE IF NOT EXISTS`, so `ALTER ROLE paz ... SET search_path =
engine, public` is what routes them. See `infra/postgres/init/10-engine-schema.sql`.

> That init script runs automatically **only on an empty data directory**. On a database
> that already has data, apply it once:
> ```bash
> docker compose exec postgres psql -U condor -d condor \
>   -f /docker-entrypoint-initdb.d/10-engine-schema.sql
> ```
> On **Git Bash for Windows**, prefix it with `MSYS_NO_PATHCONV=1` — otherwise the shell
> rewrites the container path into a Windows one and psql reports "No such file".
>
> Until it is applied the engine fails at startup with
> `InvalidPasswordError: password authentication failed for user "paz"`. That is the
> intended failure: it dies before any `CREATE TABLE`, so it can never leak its tables
> into the console's `public` schema.

### If you moved from a plain `postgres:16` volume

`pgvector/pgvector:pg16` ships a different glibc, so an existing database will warn about a
**collation version mismatch**. Left alone, text index ordering can silently disagree with
the collation it was built under. Fix it once:

```bash
docker compose exec -T postgres psql -U condor -d condor -c "REINDEX DATABASE condor;"
docker compose exec -T postgres psql -U condor -d condor -c "ALTER DATABASE condor REFRESH COLLATION VERSION;"
```

The console keeps SQLAlchemy + psycopg; the engine keeps raw asyncpg. Neither had to move.

## How the console reaches the engine

```
browser ──/api/engine/top──▶ nginx ──▶ api (session cookie checked here)
                                        └── engine_proxy.py ──▶ engine :8000
```

`apps/console/api/app/engine_proxy.py` forwards **read-only GETs only**, and every route
depends on the console's session. The engine's own Firebase auth gate is deliberately off,
because this proxy is its only door — so **the frontend must never call the engine
directly**, and no second nginx route should be added around it.

If the engine is down, every proxied route answers `{"available": false}` with HTTP 200.
The `/ideas` page renders an offline panel; nothing else in the console notices. That is a
deliberate property, and the regression test worth running after any change here:

```bash
docker compose stop engine     # /ideas degrades, everything else keeps working
docker compose start engine
```

## Repository layout

```
CLAUDE.md                  the engine + how the halves relate
docker-compose.yml         ONE compose file, both halves. `name: pazrav` is load-bearing
.env.example               merged; ANTHROPIC_API_KEY is shared by both halves
pyproject.toml             the engine package + the root pytest config
infra/postgres/init/       the schema/role bootstrap
src/paz_rav/               THE ENGINE
tests/                     engine tests (106, zero-install, no network)
web/                       the engine's own dashboard
apps/console/              THE CONSOLE — imported by git subtree, history preserved
  CLAUDE.md                console-specific invariants. Read before touching it
  api/ trading-core/ frontend/ dashboard/ observability/
  trading-core/tests/      console tests (15)
```

`apps/console` came in via `git subtree` (not `--squash`), so the console's original
history is still in this repo's object store — the old `OTSROTAY` working copy has been
deleted and this is now the only repo:

```bash
git log --oneline ab9b27c       # all 13 original console commits
git log --oneline apps/console  # commits touching that path since the merge
git remote -v                   # `console` -> github.com/adielsh/OTSROTAY, for future pulls
```

Note the first form needs the commit id: `git log -- apps/console` follows the path, not
the grafted history, so it will not list the pre-merge commits on its own.

## The IBKR feed

`PAZ_DATA=ibkr` points the engine at the **same gateway the console's daemon trades
through**, which is what makes an engine idea and a broker order comparable at all —
yfinance is a different vendor whose chains need not agree strike-for-strike with what
IBKR would fill.

It does **not** fetch greeks. The builder computes its own delta and IV from the quote
(`builder.annotate` → `analytics.iv.contract_iv` → `quant.greeks`), so the project's rule
that every number comes from deterministic Python is untouched. IBKR's model IV rides
free on the same subscription and is used only as an input to that same path.

### The constraint that shapes the whole adapter

IBKR caps concurrent market-data lines (~100 per login) and **the daemon that places
orders shares that cap**. Going over does not raise — requests silently return nothing —
so a careless scan would degrade live trading to serve a ranking engine. Hence:

| Knob | Default | Why |
|---|---|---|
| `IB_MAX_LINES` | 32 | Far below the cap, leaving the daemon room. Never opens more at once. |
| `IB_STRIKES_EACH_SIDE` | 18 | Cap per side after thinning. |
| `IB_MONEYNESS` | 0.12 | Band around spot the strikes are drawn from. |
| `IB_CLIENT_ID` | 25 | Must avoid the daemon's 11 and the console API's 12–23. |
| `SCAN_INTERVAL` | 60 | **Raise to ≥300 for this feed.** |

The strike window needs both halves. A pure percentage band is unbounded (±12% of SPY on
a $1 ladder is ~180 strikes); a pure count of the nearest strikes is far too *narrow* —
18 each side of a $769 spot reaches only ±2.3%, and a 16-delta short strike at 35 DTE
sits well outside that, so the chain came back bounded, valid and useless. The adapter
takes the band and **thins it evenly**, keeping reach at a coarser granularity.

### Measured

One underlying costs ~15–20s (two expiries, ~50 contracts each), so nine names overrun a
60-second interval. Run a short `UNDERLYINGS` list with a long `SCAN_INTERVAL`, or keep
yfinance for breadth and use IBKR for the names you would really trade.

```bash
PAZ_DATA=ibkr UNDERLYINGS=SPX,SPY SCAN_INTERVAL=300 docker compose up -d engine
```

### Four traps found by actually running it

- **IBKR returns several option classes per underlying.** For SPY it answers `2SPY` — an
  adjusted class with a sparse ladder and two expiries — alongside the real `SPY`. Taking
  the first SMART entry picked `2SPY` and every strike came back *"No security definition
  has been found"*: a chain that looked empty rather than wrong. `_pick_chain` prefers the
  PM-settled weeklies (`SPXW`, what the daemon trades), then the exactly-named class,
  breaking ties on the most complete ladder.
- **Outside RTH there is no bid/ask at all**, only `last`/`close`. That is fine — the
  builder already falls back to `last` — but it means an off-hours scan cannot be judged
  on spreads, and `rel_spread` reads 0 ("unknown"), not "tight".
- **A fixed clientId breaks on restart.** The gateway can still hold the previous session
  under that id; the next connect then returns empty quotes forever — indistinguishable
  from having no subscription. Every symbol failed until a fresh id was used. The adapter
  rotates a pool (25–34), which is what the console's `ib_bridge` already does (12–23).
- **Thin the strikes *after* qualifying, not before.** `qualifyContractsAsync` is a
  definition lookup and costs no market-data lines; only `reqMktData` does. SPX advertises
  a 744-strike ladder spanning every expiry, but a single weekly lists a coarse subset of
  it — an evenly-thinned band qualified 2 of 6 and produced nothing. Qualifying generously
  and thinning the survivors took SPX from 4 quotes to 28.
- **`min_open_interest` silently empties the chain.** IBKR's *delayed* feed does not
  populate open interest (every strike reads 0–1), so the default floor of 10 rejected
  every candidate while the scan looked perfectly healthy. `MIN_OPEN_INTEREST=0` on this
  feed, leaning on relative spread instead — knowingly, because it is a weaker gate.

## Testing

```bash
python -m pytest                                        # engine only: 106, no installs needed
pip install -e ".[console]"
python -m pytest tests apps/console/trading-core/tests  # both: 121
cd apps/console/frontend && npm run build               # tsc -b strict is the real gate
```

The engine suite deliberately needs no infrastructure, no network and no extra installs.
Keep it that way — that is why the console suite is opt-in rather than in `testpaths`.

## What has *not* been merged yet

Honest list, because "one repo" is not the same as "one system":

1. **The engine *can* now read the IB gateway, but does not by default.**
   `adapters/ibkr.py` is implemented and validated end-to-end (see below); `PAZ_DATA`
   still defaults to `yfinance` because IBKR cannot sustain the engine's default shape.
   The `/ideas` page names the live source on every scan either way.
2. **Engine candidates cannot become trades.** The console has the whole approval pipeline —
   proposal card, re-price-and-re-validate, order path — pointed at one hard-coded SPX
   condor. Feeding it the engine's ranked candidates is a database write, not a new feature.
3. **Two auth systems.** The console's argon2/JWT accounts are the only login. The engine's
   Firebase gate is still in the code but switched off; `web/` on :8010 still imports it, so
   it can't be deleted until those pages are migrated.
4. **Two frontends.** `web/` is unchanged and still served. Its pages migrate into the
   console one at a time; nothing forces a big-bang rewrite.
