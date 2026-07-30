"""Seed a realistic *demo* history so the analytics UI has meaningful data.

NOT real trades — a plausible simulation of the strategy over ~9 months for charting/QA.
Run:  docker compose run --rm --no-deps trading-core python -m app.seed_demo
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from . import db
from .config import CONFIG

random.seed(42)
N = 92                       # historical trades
START = datetime.now(timezone.utc) - timedelta(days=270)


def _regime():
    """Pick a VIX and the matching target deltas (mirrors the state machine)."""
    vix = round(random.uniform(11.0, 25.5), 1)
    d = CONFIG.target_deltas(vix)
    if d is None:                       # VIX>22 would suspend live; for demo keep mid band
        return vix, (0.30, 0.20)
    return vix, d


def run() -> None:
    S = db.init_db()
    with S() as s:
        # Wipe prior demo rows only — real trades/gates (is_demo=False) are never touched by
        # this script, even if it's re-run against a DB the live daemon is also using.
        demo_trade_ids = [t.id for t in s.query(db.Trade.id).filter_by(is_demo=True)]
        if demo_trade_ids:
            s.query(db.Pnl).filter(db.Pnl.trade_id.in_(demo_trade_ids)).delete(synchronize_session=False)
            s.query(db.Fill).filter(db.Fill.trade_id.in_(demo_trade_ids)).delete(synchronize_session=False)
        s.query(db.Trade).filter_by(is_demo=True).delete(synchronize_session=False)
        s.query(db.GateDecision).filter_by(is_demo=True).delete(synchronize_session=False)
        s.commit()

    spot = 5300.0
    with S() as s:
        for i in range(N):
            opened = START + timedelta(days=i * 2.9 + random.uniform(0, 1))
            spot += random.uniform(-45, 55)                 # drifting index
            vix, (pd_, cd_) = _regime()
            credit = round(random.uniform(1.20, 1.72), 2)
            dte0 = random.randint(38, 45)
            # short strikes scaled off spot; wider puts (skew), fixed 50-pt wings
            ps = round((spot - random.uniform(140, 220)) / 5) * 5
            cs = round((spot + random.uniform(150, 240)) / 5) * 5
            pl, cl = ps - CONFIG.wing_width, cs + CONFIG.wing_width

            r = random.random()
            hold = random.randint(6, 20)
            closed = opened + timedelta(days=hold)
            if r < 0.70:                    # take-profit hit
                status, realized, close_kind = "closed", 50.0, "take_profit"
            elif r < 0.82:                  # expired worthless -> keep full credit
                status, realized, close_kind = "expired", round(credit * 100, 2), "expire"
                closed = opened + timedelta(days=dte0)
            else:                           # tested -> gamma/stop loss
                status, realized, close_kind = "stopped", -round(random.uniform(110, 430), 2), "gamma_exit"

            t = db.Trade(
                created_at=opened, closed_at=closed, expiry=(opened + timedelta(days=dte0)).strftime("%Y%m%d"),
                dte=dte0, vix_avg=vix, put_short_strike=ps, put_long_strike=pl,
                call_short_strike=cs, call_long_strike=cl, target_put_delta=pd_, target_call_delta=cd_,
                entry_credit=credit, quantity=1, status=status, leg_conids=[i * 4 + k for k in range(4)],
                is_demo=True,
            )
            s.add(t); s.flush()
            s.add(db.Fill(trade_id=t.id, kind="entry", price=credit, quantity=1, ts=opened))
            close_debit = round(credit - realized / 100, 2)
            s.add(db.Fill(trade_id=t.id, kind=close_kind, price=max(close_debit, 0), quantity=1, ts=closed))
            s.add(db.Pnl(trade_id=t.id, realized=realized, computed_at=closed))

        # a few still-open positions (no pnl yet)
        for j in range(3):
            opened = datetime.now(timezone.utc) - timedelta(days=j * 4 + 2)
            vix, (pd_, cd_) = _regime()
            ps = round((spot - 180) / 5) * 5; cs = round((spot + 200) / 5) * 5
            t = db.Trade(
                created_at=opened, expiry=(opened + timedelta(days=42)).strftime("%Y%m%d"),
                dte=42 - j * 3, vix_avg=vix, put_short_strike=ps, put_long_strike=ps - 50,
                call_short_strike=cs, call_long_strike=cs + 50, target_put_delta=pd_, target_call_delta=cd_,
                entry_credit=round(random.uniform(1.25, 1.6), 2), quantity=1, status="open",
                leg_conids=[9000 + j * 4 + k for k in range(4)],
                is_demo=True,
            )
            s.add(t); s.flush()
            s.add(db.Fill(trade_id=t.id, kind="entry", price=t.entry_credit, quantity=1, ts=opened))

        # gate decisions (accepts + a spread of realistic rejects)
        reasons = [
            (True, "ok"), (True, "ok"), (True, "ok"), (True, "ok"),
            (False, "VIX>22 systemic volatility suspend"),
            (False, "min-credit 1.05 < 1.20"),
            (False, "liquidity spread 1.75 > 1.50"),
            (False, "pyramiding: overlapping short strike 6200"),
            (False, "margin add 8200.00 > budget 7900.00"),
        ]
        for k in range(60):
            when = START + timedelta(days=k * 4.4)
            acc, reason = random.choice(reasons)
            vix = round(random.uniform(11, 26), 1)
            s.add(db.GateDecision(created_at=when, vix=vix, accepted=acc, reason=reason,
                                  details={"vix": vix, "credit_mid": round(random.uniform(1.0, 1.7), 2)},
                                  is_demo=True))
        s.commit()

    with S() as s:
        demo_ids = [t.id for t in s.query(db.Trade.id).filter_by(is_demo=True)]
        print("demo trades:", len(demo_ids),
              "demo pnl:", s.query(db.Pnl).filter(db.Pnl.trade_id.in_(demo_ids)).count(),
              "demo gates:", s.query(db.GateDecision).filter_by(is_demo=True).count())


if __name__ == "__main__":
    run()
