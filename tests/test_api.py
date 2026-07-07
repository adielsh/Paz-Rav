"""API + WebSocket — driven with FastAPI's TestClient on the fixture feed (no network)."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from paz_rav.adapters.market_data import ReplayMarketData
from paz_rav.api.app import create_app
from paz_rav.strategies import BuildConfig

FIXTURE = Path(__file__).parent / "fixtures" / "sample_market.json"
TODAY = date(2026, 1, 15)


def make_client() -> TestClient:
    app = create_app(
        feed=ReplayMarketData(FIXTURE), underlyings=["SPY"], interval=3600, today=TODAY,
        config=BuildConfig(short_deltas=(16.0, 25.0), wing_widths=(5.0, 10.0),
                           max_rel_spread=0.6, top_n=6),
    )
    return TestClient(app)


def test_health():
    with make_client() as c:
        assert c.get("/health").json()["status"] == "ok"


def test_state_has_feature_and_candidates():
    with make_client() as c:
        st = c.get("/api/state").json()
        assert any(f["underlying"] == "SPY" for f in st["features"])
        assert st["candidates"]["SPY"], "expected candidates for SPY"


def test_candidates_endpoint():
    with make_client() as c:
        r = c.get("/api/candidates/SPY").json()
        assert r["underlying"] == "SPY"
        assert len(r["candidates"]) >= 1


def test_payoff_endpoint_shape():
    with make_client() as c:
        r = c.get("/api/payoff/SPY/0").json()
        pnls = [p["pnl"] for p in r["points"]]
        assert len(pnls) == 61
        assert max(pnls) > 0 and min(pnls) < 0   # profit tent with losing wings


def test_ws_sends_snapshot():
    with make_client() as c:
        with c.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
            assert "SPY" in msg["candidates"]


def test_top_excludes_pass_verdicts():
    with make_client() as c:
        r = c.get("/api/top?n=5").json()
        assert r["groups"], "expected at least one strategy group"
        for g in r["groups"]:
            for t in g["trades"]:
                assert t["verdict"] != "pass"  # committee-rejected trades never surface here


def test_top_ranks_take_before_caution():
    with make_client() as c:
        r = c.get("/api/top?n=6").json()
        rank = {"take": 0, "caution": 1}
        for g in r["groups"]:
            ranks = [rank[t["verdict"]] for t in g["trades"]]
            assert ranks == sorted(ranks), (
                f"{g['strategy']}: a 'caution' trade outranked a 'take' trade")


def test_top_caps_repeats_of_the_same_underlying():
    """Ten strike-variants of one name are near-duplicates of the same market view —
    /api/top must keep at most 2 per underlying per strategy so the list stays diverse."""
    with make_client() as c:
        r = c.get("/api/top?n=10").json()
        for g in r["groups"]:
            per: dict[str, int] = {}
            for t in g["trades"]:
                per[t["underlying"]] = per.get(t["underlying"], 0) + 1
            assert all(v <= 2 for v in per.values()), f"{g['strategy']}: {per}"


def test_open_position_and_list(monkeypatch):
    with make_client() as c:
        opened = c.post("/api/positions/open/SPY/0").json()
        assert opened["status"] == "open"
        assert opened["underlying"] == "SPY"
        assert "id" in opened

        rows = c.get("/api/positions").json()["positions"]
        assert any(p["id"] == opened["id"] for p in rows)
        mine = next(p for p in rows if p["id"] == opened["id"])
        assert mine["status"] == "open"
        assert "unrealized_pnl" in mine   # live mark-to-market for an open position


def test_manual_close_records_real_price():
    with make_client() as c:
        opened = c.post("/api/positions/open/SPY/0").json()
        closed = c.post(f"/api/positions/{opened['id']}/close",
                        json={"exit_credit": -1.5}).json()
        assert closed["status"] == "closed"
        assert closed["exit_credit"] == -1.5
        assert closed["realized_pnl"] == round(opened["entry_credit"] - 1.5, 4)

        rows = c.get("/api/positions").json()["positions"]
        mine = next(p for p in rows if p["id"] == opened["id"])
        assert mine["status"] == "closed"
