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

`apps/console` came in via `git subtree`, so its full history is reachable:
```bash
git log apps/console            # every OTSROTAY commit
git remote -v                   # `console` -> the original repo, for future pulls
```

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

1. **The engine still runs on delayed yfinance data**, not the IB gateway sitting next to it.
   `adapters/ibkr.py` is a stub with the right 4-method shape;
   `apps/console/trading-core/app/data_fetcher.py` already implements every one of those
   reads against `ib_async`. This is the highest-value next step, and until it lands the
   `/ideas` page labels its data source on every scan.
2. **Engine candidates cannot become trades.** The console has the whole approval pipeline —
   proposal card, re-price-and-re-validate, order path — pointed at one hard-coded SPX
   condor. Feeding it the engine's ranked candidates is a database write, not a new feature.
3. **Two auth systems.** The console's argon2/JWT accounts are the only login. The engine's
   Firebase gate is still in the code but switched off; `web/` on :8010 still imports it, so
   it can't be deleted until those pages are migrated.
4. **Two frontends.** `web/` is unchanged and still served. Its pages migrate into the
   console one at a time; nothing forces a big-bang rewrite.
