# CLAUDE.md — apps/console

Guidance for the **console** half of this monorepo. The engine half (`src/paz_rav/`) is
covered by the root `CLAUDE.md`; read that first for how the two fit together.

## What this is

An SPX (SPXW, PM-settled) **iron-condor trading platform** on the Interactive Brokers API.
Fully mechanical — every decision is a rule you can read in the source and an audit row in
Postgres. Unlike the engine, this half **actually trades**. Full rationale is in
`README.md`, the strategy spec in `PRD.md`.

The stack is driven from the **repository root**, not from here:
```bash
cd ../..              # repo root
docker compose up -d --build
```
There is one `docker-compose.yml`, at the root. Don't add another.

## The safety model — do not weaken any of this

Four independent locks, all of which must be released before an order reaches IBKR:

1. **`PLACE_ORDERS`** (default `0`) — dry run. Gates are evaluated and persisted; nothing
   is transmitted.
2. **`REQUIRE_APPROVAL`** (default `1`) — a condor that passes every gate is written to
   `trade_proposals` and waits for a human. On approval the daemon **re-prices and
   re-validates** (fresh credit, fresh `whatIf` margin for the approved quantity, kill
   switch re-checked) — a stale quote can never be traded.
3. **Paper-account guard** — `trading-core` refuses to start unless the connected account
   starts with `DU` (`PAPER_ACCOUNT_PREFIX`).
4. **Kill switch** — `control.trading_enabled`, polled before every entry, flipped from the
   console header.

**`trading-core` is the only service that may place an order.** The `api` service reads the
database and flips status columns; it holds a read-only IB client (`ib_bridge.py`, rotating
clientIds 12–23 so it never collides with the daemon's 11) and has no route that could move
money. Keep it that way — a bug in the web layer must never be able to trade.

> Exits are **not** gated by approval. Once a position is open, the GTC take-profit and the
> 25-DTE gamma stop act autonomously, by design. Don't add a click in front of a stop.

`engine_proxy.py` forwards read-only GETs to the Paz Rav engine. That is safe *because* the
engine is advisory — it has no broker connection and no order route. If the engine ever
gains one, this proxy is the thing to re-examine first.

## Two rules about money, both of which were bugs worth fixing

- **P&L is per position, never per leg.** A four-leg condor nets to one number. One leg of a
  January SPX spread showed `+$72,840` while its position actually netted `−$2,129`.
- **P&L is attributed to the close date**, not the open date — that is when the money was
  booked, and it is how IBKR reports it. The console reconciles against the broker exactly.
- Returns are **time-weighted and deposit-adjusted**, compounded from IBKR's daily NAV
  blocks, so a mid-period deposit is never counted as performance.

## Backend layout

```
api/app/
  main.py           reporting API, approvals, kill switch, router wiring
  auth.py           argon2 accounts, JWT-in-cookie sessions, encrypted broker creds
  ib_bridge.py      read-only live IB bridge (never places orders)
  flex.py           IBKR Flex statement ingest + per-user Postgres cache
  chat.py           the grounded in-console assistant
  engine_proxy.py   read-only proxy to the Paz Rav engine, behind the session cookie

trading-core/app/
  main.py           daemon loop, entry flow, proposals, state recovery
  data_fetcher.py   IB read layer: chain, greeks, quotes, halt guards
  risk_manager.py   the pre-flight gates
  execution.py      combo orders, limit walks, GTC take-profit
  config.py         all strategy parameters, as constants
  db.py             SQLAlchemy models — the schema owner
```

**Routers are factory functions** (`build_router(engine, USER_ID)`), not module-level
`APIRouter`s, deliberately: it avoids a circular import between `main` and the routers, and
it makes the auth dependency explicit at the registration site. `ib_bridge.router` is the
one exception. Follow the factory pattern when adding a router.

**Schema ownership:** `trading-core/app/db.py` owns the schema via
`Base.metadata.create_all`. `api/app/main.py` re-declares `trade_proposals` and
`nav_snapshots` as `CREATE TABLE IF NOT EXISTS` so the API works even if the daemon has
never booted. **A column added to the ORM must be hand-copied into that SQL** — there is no
migration tool, and `create_all` does not add columns to an existing table (see
`_ensure_owner_columns` for the defensive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
pattern to follow).

These tables live in Postgres schema **`public`**. The engine's live in `engine`. Same
database, different roles — see the root `CLAUDE.md`.

## Frontend (`frontend/`)

React 18 + Vite + Redux Toolkit + RTK Query + AG Grid Community + Recharts. Nine runtime
deps and **no CSS framework** — the entire design system is one hand-written file,
`src/index.css` (~1,290 lines), driven by CSS custom properties.

**The palette is mirrored in three files and they must be changed together:**
1. `src/index.css` — the canonical CSS variables, both themes.
2. `src/lib/chartTheme.ts` — literal hex for Recharts (SVG attributes can't resolve vars).
3. `src/components/DataGrid.tsx` — AG Grid `themeQuartz.withParams()`, its own hex mirror.

Other things that will bite you:

- **`he` translations are compiler-enforced.** `en` is the source of truth and
  `TKey = keyof typeof en`; `he: Record<TKey, string>` means a missing Hebrew string is a
  build error, not a silent fallback. Adding a label costs a Hebrew string. This is a
  feature — don't work around it.
- **`tsc -b` runs with `strict`** (`npm run build` is `tsc -b && vite build`).
  `noUnusedLocals`/`noUnusedParameters` are off here, unlike the engine's `web/`.
- **Numbers are pinned LTR** (`direction: ltr; unicode-bidi: isolate` on `.pnl`, `.g-num`,
  `.cell .v`) so a leading `−` on a loss is never bidi-reordered to the end under Hebrew.
- **AG Grid Community has no master/detail.** Expandable rows are faked by injecting a
  synthetic `__detail` row and using `isFullWidthRow` + `fullWidthCellRenderer` — see
  `pages/RealAccount.tsx` and `pages/Ideas.tsx`.
- **Adding a page is five small edits:** the page file, a `<Route>` in `App.tsx`, a `NAV` +
  `TITLE` entry in `components/Layout.tsx`, keys in `i18n/translations.ts`, and endpoints in
  the single `store/api.ts` slice. Compose from `Cluster`/`Panel`/`DataGrid`/`Pill`/`PnL`
  and you need no new CSS.
- **`Layout.tsx` derives `mode` from the route** (`pathname === "/real" ? "real" : "demo"`).
  Any new route silently reads as "demo". It only affects which segmented button is
  highlighted, so it is cosmetic — but know it before you go looking for the bug.
- `@tanstack/react-table` is in `package.json` and imported nowhere. Safe to drop.

**Auth flow:** an httpOnly cookie (`condor_session`, JWT HS256, `samesite=lax`). The
frontend never sees a token — `fetchBaseQuery({ credentials: "include" })` carries it. There
is no 401 interceptor: `useMeQuery` failing on mount is what falls the shell back to
`<Login/>`. The whole router sits behind that one gate, so no page can flash a prior
session's cached data.

## Testing

```bash
cd trading-core && python -m pytest tests/ -q      # 15 tests, pure logic
cd frontend && npm run build                        # tsc -b is the real gate
```

`trading-core/tests/test_pure_logic.py` covers tick rounding, the VIX→delta bands, DTE
maths, the CBOE calendar, and a sqlite round-trip of the ORM. **Not covered:**
`risk_manager` gates, `execution.py`'s sign convention, `data_fetcher`, the proposal state
machine, and all of `api/app/`. Bear that in mind before trusting a refactor there.

`app.verify_sign` (`docker exec condor-core python -m app.verify_sign`) is a **read-only**
`whatIfOrderAsync` probe that settles the order sign convention (`BUY` at a negative limit
opens for a credit) without transmitting anything. Run it rather than reasoning about it.
