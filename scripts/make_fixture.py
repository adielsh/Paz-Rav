"""Generate a deterministic multi-underlying market fixture for tests + offline demos.

Prices come from Black-Scholes so each chain is internally consistent (short strikes
richer than long), letting the builder produce real condors and diagonals with no
network. Writes tests/fixtures/sample_market.json.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from paz_rav.quant import black_scholes

AS_OF = date(2026, 1, 15)
TS = datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc).isoformat()
R = 0.04
EXPIRIES = [date(2026, 3, 1), date(2026, 3, 31)]

# symbol -> (spot, IV). ETFs + big single names, varied vols so the Top-5 spans
# names AND strategies (low IV favours DACS, high IV favours the condor).
# SPY stays spot 100 (the test suite asserts it).
UNDERLYINGS = {
    "SPX": (6000.0, 0.13),   # index — the primary iron-condor name
    "SPY": (100.0, 0.20),
    "QQQ": (130.0, 0.22),
    "IWM": (75.0, 0.30),
    "NVDA": (135.0, 0.45),
    "MSFT": (440.0, 0.22),
    "GOOGL": (180.0, 0.26),
    "AMZN": (200.0, 0.30),
    "CSCO": (60.0, 0.20),
}


def _step(spot: float) -> int:
    for lim, st in ((50, 1), (150, 5), (300, 5), (700, 10), (2000, 25), (10 ** 9, 50)):
        if spot < lim:
            return st
    return 50


def _strikes(spot: float) -> list[float]:
    step = _step(spot)
    lo = round(spot * 0.70 / step) * step
    hi = round(spot * 1.30 / step) * step
    return [float(k) for k in range(int(lo), int(hi) + step, step)]


def build() -> dict:
    underlyings, chains = {}, {}
    for sym, (spot, iv) in UNDERLYINGS.items():
        underlyings[sym] = {"price": spot, "ts": TS}
        rows = []
        for expiry in EXPIRIES:
            t = (expiry - AS_OF).days / 365.0
            for k in _strikes(spot):
                for right in ("call", "put"):
                    price = black_scholes(spot, k, t, R, iv, right)
                    spread = max(price * 0.02, 0.01)
                    rows.append({
                        "underlying": sym, "right": right, "strike": k,
                        "expiry": expiry.isoformat(),
                        "bid": round(max(price - spread / 2, 0.01), 2),
                        "ask": round(price + spread / 2, 2),
                        "last": round(price, 2),
                        "open_interest": 500, "implied_vol": iv, "ts": TS,
                    })
        chains[sym] = rows
    return {"underlyings": underlyings, "chains": chains}


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_market.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(f"wrote {out}  ({', '.join(UNDERLYINGS)})")
