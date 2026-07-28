"""Persistence layer: SQLAlchemy models + session factory.

Postgres in production; SQLite works for unit tests (generic JSON type). This is a durable second
source of truth alongside IBKR, and the schema is kept flat/queryable so a future AI analytics or
NL-assistant layer can read it directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

from .config import CONFIG


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expiry: Mapped[str] = mapped_column(String(8))                 # YYYYMMDD
    dte: Mapped[int] = mapped_column(Integer)
    vix_avg: Mapped[float] = mapped_column(Float)
    put_short_strike: Mapped[float] = mapped_column(Float)
    put_long_strike: Mapped[float] = mapped_column(Float)
    call_short_strike: Mapped[float] = mapped_column(Float)
    call_long_strike: Mapped[float] = mapped_column(Float)
    target_put_delta: Mapped[float] = mapped_column(Float)
    target_call_delta: Mapped[float] = mapped_column(Float)
    entry_credit: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=CONFIG.lot_size)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|closed|expired|stopped
    ib_perm_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leg_conids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fills: Mapped[list["Fill"]] = relationship(back_populates="trade", cascade="all, delete-orphan")


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"))
    kind: Mapped[str] = mapped_column(String(16))     # entry|take_profit|gamma_exit
    price: Mapped[float] = mapped_column(Float)        # net combo price (credit positive)
    quantity: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    trade: Mapped[Trade] = relationship(back_populates="fills")


class GateDecision(Base):
    __tablename__ = "gate_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    vix: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(255))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # per-gate values


class Pnl(Base):
    __tablename__ = "pnl"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), unique=True)
    realized: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TradeProposal(Base):
    """A condor the gates approved, parked for a human decision instead of being placed.

    The daemon writes proposals (status='pending'); the API only ever flips status to
    'approved'/'rejected' — it never talks to IB. The daemon picks approved rows up on its
    next poll, re-validates and re-prices them, then places. That keeps the existing
    "API cannot move money" property intact while putting a person in the loop.
    """
    __tablename__ = "trade_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # pending -> approved -> placed | failed ; or pending -> rejected | expired
    status: Mapped[str] = mapped_column(String(16), default="pending")

    expiry: Mapped[str] = mapped_column(String(8))
    dte: Mapped[int] = mapped_column(Integer)
    vix_avg: Mapped[float] = mapped_column(Float)
    put_short_strike: Mapped[float] = mapped_column(Float)
    put_long_strike: Mapped[float] = mapped_column(Float)
    call_short_strike: Mapped[float] = mapped_column(Float)
    call_long_strike: Mapped[float] = mapped_column(Float)
    target_put_delta: Mapped[float] = mapped_column(Float)
    target_call_delta: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=CONFIG.lot_size)

    # Pricing snapshot at proposal time. Re-priced before placing — quotes go stale.
    combo_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    combo_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    combo_mid: Mapped[float | None] = mapped_column(Float, nullable=True)
    combo_spread: Mapped[float | None] = mapped_column(Float, nullable=True)

    leg_conids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gate_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Set once the approved proposal actually results in a fill, or fails to.
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    placed_credit: Mapped[float | None] = mapped_column(Float, nullable=True)


class Control(Base):
    """Single-row control table. The daemon polls trading_enabled before each entry; the API flips it."""
    __tablename__ = "control"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


_engine = None
_Session: sessionmaker | None = None


def init_db(dsn: str | None = None, echo: bool = False):
    """Create engine, tables, and ensure the singleton control row exists. Returns the sessionmaker."""
    global _engine, _Session
    _engine = create_engine(dsn or CONFIG.db_dsn, echo=echo, future=True)
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    with _Session() as s:
        if s.get(Control, 1) is None:
            s.add(Control(id=1, trading_enabled=True, updated_by="init"))
            s.commit()
    return _Session


def get_session() -> Session:
    if _Session is None:
        raise RuntimeError("init_db() must be called before get_session()")
    return _Session()


def trading_enabled() -> bool:
    with get_session() as s:
        ctrl = s.get(Control, 1)
        return bool(ctrl and ctrl.trading_enabled)
