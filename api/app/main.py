"""Read-only reporting API over the condor Postgres DB, plus the kill-switch write.

Intentionally decoupled from IB: it only reads/writes the database (plain SQL), so it can never
place or affect orders directly. The only mutation is flipping control.trading_enabled — the
trading-core daemon polls that flag before each entry.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from . import auth, chat, ib_bridge, flex

DB_DSN = os.getenv("DB_DSN", "postgresql+psycopg://condor:condor@127.0.0.1:5432/condor")
engine = create_engine(DB_DSN, future=True, pool_pre_ping=True)


def _ensure_nav_table() -> None:
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS nav_snapshots ("
            "id serial PRIMARY KEY, ts timestamptz DEFAULT now(), "
            "net_liq double precision, daily_pnl double precision, unrealized double precision)"))


def _ensure_owner_columns() -> None:
    """Row-level isolation, applied defensively.

    trading-core owns this schema and runs the same migration, but the two services start
    independently and the API must never serve a query against a table that has not got the
    column yet — that would fail closed with a 500 rather than open, but a boot-order race
    is not something to leave to chance. Idempotent.
    """
    owned = ("trades", "gate_decisions", "trade_proposals", "control", "nav_snapshots")
    with engine.begin() as c:
        for table in owned:
            c.execute(text(
                f"ALTER TABLE IF EXISTS {table} ADD COLUMN IF NOT EXISTS user_id integer"))
            c.execute(text(
                f"CREATE INDEX IF NOT EXISTS {table}_user_idx ON {table} (user_id)"))
        owner = c.execute(text(
            "SELECT id FROM users WHERE role = 'owner' ORDER BY id LIMIT 1")).scalar()
        if owner is not None:
            for table in owned:
                c.execute(text(f"UPDATE {table} SET user_id = :o WHERE user_id IS NULL"),
                          {"o": owner})


def _owner_id() -> int | None:
    with engine.connect() as c:
        return c.execute(text(
            "SELECT id FROM users WHERE role = 'owner' ORDER BY id LIMIT 1")).scalar()


def _ensure_proposals_table() -> None:
    """Mirror of trading-core's TradeProposal model so the API works even if the daemon has
    never booted. trading-core owns the schema; this is CREATE IF NOT EXISTS only."""
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS trade_proposals ("
            "id serial PRIMARY KEY, created_at timestamptz DEFAULT now(), "
            "status varchar(16) DEFAULT 'pending', "
            "expiry varchar(8), dte integer, vix_avg double precision, "
            "put_short_strike double precision, put_long_strike double precision, "
            "call_short_strike double precision, call_long_strike double precision, "
            "target_put_delta double precision, target_call_delta double precision, "
            "quantity integer, combo_bid double precision, combo_ask double precision, "
            "combo_mid double precision, combo_spread double precision, "
            "leg_conids json, gate_details json, "
            "expires_at timestamptz, decided_at timestamptz, decided_by varchar(64), "
            "note varchar(255), trade_id integer, error varchar(255), "
            "placed_credit double precision)"))


# Auth wiring: dependencies are built against this engine, then handed to the routers
# that need them so no module has to import the app itself.
auth.ensure_tables(engine)
USER_ID, USER_CREDS = auth.make_dependencies(engine)


def OWNER_ONLY(uid: int = Depends(USER_ID)) -> int:
    """Guards the endpoints backed by the single shared broker connection.

    ib_bridge holds one IB client against one gateway and one account, so /ib/* is not
    per-user data and cannot be filtered into being. Rather than quietly showing every
    signed-in user the owner's broker account, say no. This is what lifts when a second
    broker connection exists, not something to paper over with a WHERE clause.
    """
    owner = _owner_id()
    if owner is None or uid != owner:
        raise HTTPException(403, "this view belongs to the account that owns the broker "
                                 "connection")
    return uid



@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_nav_table()
    _ensure_proposals_table()
    _ensure_owner_columns()
    await ib_bridge.startup()      # best-effort connect to the paper gateway (read-only)
    yield
    await ib_bridge.shutdown()


app = FastAPI(title="SPX Condor API", version="0.1.0", lifespan=lifespan)
# Credentials travel in a cookie, so the browser must be allowed to send them and the
# origin can no longer be a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080").split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.build_router(engine, USER_ID))
# One IB client, one gateway, one account — so these are the owner's, explicitly.
app.include_router(ib_bridge.router, dependencies=[Depends(OWNER_ONLY)])
app.include_router(flex.build_router(USER_CREDS))
# The assistant reads the same two sources the console renders — Postgres and this user's
# cached Flex statement — and is handed them as an already-computed snapshot.
app.include_router(chat.build_router(engine, USER_ID, USER_CREDS, flex._user_cache_read,
                                    lambda uid: uid == _owner_id()))


def _rows(sql: str, **params) -> list[dict]:
    with engine.connect() as c:
        return [dict(r) for r in c.execute(text(sql), params).mappings().all()]


@app.get("/health")
def health() -> dict:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(503, f"db unavailable: {e}")


@app.get("/positions")
def positions(uid: int = Depends(USER_ID)) -> list[dict]:
    """Open condors (durable view from the DB; IBKR remains the settlement source of truth).

    Excludes seed_demo.py rows (is_demo=true) — those aren't real positions."""
    return _rows(
        "SELECT * FROM trades WHERE user_id = :uid AND status = 'open' "
        "AND is_demo IS NOT TRUE ORDER BY created_at DESC", uid=uid)


@app.get("/trades")
def trades(limit: int = 500, uid: int = Depends(USER_ID)) -> list[dict]:
    # LEFT JOIN realized P&L so the UI can compute win rate, avg win/loss, distributions.
    return _rows(
        "SELECT t.*, p.realized AS realized "
        "FROM trades t LEFT JOIN pnl p ON p.trade_id = t.id "
        "WHERE t.user_id = :uid "
        "ORDER BY t.created_at DESC LIMIT :limit", limit=limit, uid=uid)


@app.get("/gate-decisions")
def gate_decisions(limit: int = 100, uid: int = Depends(USER_ID)) -> list[dict]:
    return _rows("SELECT * FROM gate_decisions WHERE user_id = :uid "
                 "ORDER BY created_at DESC LIMIT :limit", limit=limit, uid=uid)


@app.get("/pnl")
def pnl(uid: int = Depends(USER_ID)) -> dict:
    rows = _rows("SELECT COALESCE(SUM(p.realized),0) AS total, COUNT(*) AS closed "
                 "FROM pnl p JOIN trades t ON t.id = p.trade_id WHERE t.user_id = :uid",
                 uid=uid)
    return rows[0] if rows else {"total": 0, "closed": 0}


@app.get("/pnl-series")
def pnl_series(uid: int = Depends(USER_ID)) -> list[dict]:
    """Realized P&L points over time (frontend builds the cumulative equity curve)."""
    return _rows("SELECT p.computed_at, p.realized FROM pnl p "
                 "JOIN trades t ON t.id = p.trade_id WHERE t.user_id = :uid "
                 "ORDER BY p.computed_at ASC", uid=uid)


@app.get("/control")
def get_control(uid: int = Depends(USER_ID)) -> dict:
    """The kill switch for this user's daemon.

    Only the owner has one today — there is a single daemon and a single broker connection —
    so everyone else gets available=false rather than a switch that would toggle a row
    nothing reads. The console hides the control in that case instead of showing a lie.
    """
    rows = _rows("SELECT * FROM control WHERE user_id = :uid", uid=uid)
    if not rows:
        return {"available": False, "trading_enabled": None}
    return {**rows[0], "available": True}


@app.get("/ib/nav-series")
async def nav_series(uid: int = Depends(OWNER_ONLY)) -> dict:
    """Real NAV time-series for the paper account. Records a snapshot (max ~1/hour) on each call
    so a genuine day/month/quarter/year curve builds up over time, then returns the whole series."""
    live = await ib_bridge.current_nav_pnl()
    if live.get("connected") and live.get("net_liq") is not None:
        with engine.begin() as c:
            last = c.execute(text("SELECT ts FROM nav_snapshots ORDER BY ts DESC LIMIT 1")).scalar()
            fresh = last is not None and (__import__("datetime").datetime.now(last.tzinfo) - last).total_seconds() < 3600
            if not fresh:
                c.execute(text("INSERT INTO nav_snapshots "
                               "(user_id, net_liq, daily_pnl, unrealized) "
                               "VALUES (:i, :n, :d, :u)"),
                          {"i": uid, "n": live["net_liq"], "d": live.get("daily"),
                           "u": live.get("unrealized")})
    series = _rows("SELECT ts, net_liq, daily_pnl, unrealized FROM nav_snapshots "
                   "WHERE user_id = :uid ORDER BY ts ASC", uid=uid)
    return {"connected": bool(live.get("connected")), "live": live, "series": series}


@app.get("/proposals")
def proposals(limit: int = 100, uid: int = Depends(USER_ID)) -> list[dict]:
    """Entries the gates approved that are waiting on a human decision (plus recent history)."""
    return _rows(
        "SELECT * FROM trade_proposals WHERE user_id = :uid "
        "ORDER BY (status = 'pending') DESC, created_at DESC LIMIT :limit",
        limit=limit, uid=uid)


MAX_LOTS = int(os.getenv("MAX_APPROVAL_LOTS", "20"))


class ProposalDecision(BaseModel):
    note: str | None = None
    decided_by: str | None = "ui"
    # How many lots to open. Bounded here so a fat-fingered value can't reach the broker;
    # the daemon still re-checks the margin for the chosen size before transmitting.
    quantity: int | None = None


def _decide(proposal_id: int, status: str, body: ProposalDecision, uid: int) -> dict:
    """Flip a pending proposal to approved/rejected.

    This writes a status column and nothing else — the API never places orders. The daemon,
    which owns the IB connection, picks approved rows up on its next poll and re-validates
    them before transmitting. The guard on status='pending' makes the decision idempotent
    and stops a double-click from re-approving something already in flight.
    """
    qty = body.quantity
    if qty is not None and not (1 <= qty <= MAX_LOTS):
        raise HTTPException(422, f"quantity must be between 1 and {MAX_LOTS}")
    with engine.begin() as c:
        # The user_id predicate is the authorisation check: approving someone else's condor
        # would put real money to work in their account.
        updated = c.execute(text(
            "UPDATE trade_proposals SET status=:s, decided_at=now(), decided_by=:by, note=:n, "
            "quantity=COALESCE(:q, quantity) "
            "WHERE id=:id AND user_id=:uid AND status='pending' RETURNING id"),
            {"s": status, "by": body.decided_by, "n": body.note, "q": qty,
             "id": proposal_id, "uid": uid}).first()
    if updated is None:
        rows = _rows("SELECT status FROM trade_proposals WHERE id = :id AND user_id = :uid",
                     id=proposal_id, uid=uid)
        if not rows:
            # Same answer for "does not exist" and "is not yours" — the distinction would
            # leak that another account holds that id.
            raise HTTPException(404, f"proposal {proposal_id} not found")
        raise HTTPException(409, f"proposal {proposal_id} is already {rows[0]['status']}")
    return _rows("SELECT * FROM trade_proposals WHERE id = :id AND user_id = :uid",
                 id=proposal_id, uid=uid)[0]


@app.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int, body: ProposalDecision,
                     uid: int = Depends(USER_ID)) -> dict:
    return _decide(proposal_id, "approved", body, uid)


@app.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, body: ProposalDecision,
                    uid: int = Depends(USER_ID)) -> dict:
    return _decide(proposal_id, "rejected", body, uid)


class KillSwitch(BaseModel):
    trading_enabled: bool
    notes: str | None = None
    updated_by: str | None = "api"


@app.post("/control")
def set_control(body: KillSwitch, uid: int = Depends(USER_ID)) -> dict:
    with engine.begin() as c:
        changed = c.execute(text(
            "UPDATE control SET trading_enabled=:e, notes=:n, updated_by=:u, updated_at=now() "
            "WHERE user_id = :uid RETURNING id"),
            {"e": body.trading_enabled, "n": body.notes, "u": body.updated_by,
             "uid": uid}).first()
    if changed is None:
        raise HTTPException(404, "you have no daemon to switch")
    return get_control(uid)
