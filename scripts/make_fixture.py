"""Generate a deterministic market fixture for tests and offline demos.

Prices come from Black-Scholes so the chain is internally consistent (short strikes
richer than long), which lets the builder produce real condors with no network.
Writes tests/fixtures/sample_market.json.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from paz_rav.quant import black_scholes

AS_OF = date(2026, 1, 15)
TS = datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc).isoformat()
SPOT = 100.0
IV = 0.20
R = 0.04
STRIKES = [float(k) for k in range(80, 121, 5)]
EXPIRIES = [date(2026, 3, 1), date(2026, 3, 31)]


def build() -> dict:
    rows = []
    for expiry in EXPIRIES:
        t = (expiry - AS_OF).days / 365.0
        for k in STRIKES:
            for right in ("call", "put"):
                price = black_scholes(SPOT, k, t, R, IV, right)
                spread = max(price * 0.02, 0.01)
                rows.append({
                    "underlying": "SPY",
                    "right": right,
                    "strike": k,
                    "expiry": expiry.isoformat(),
                    "bid": round(max(price - spread / 2, 0.01), 2),
                    "ask": round(price + spread / 2, 2),
                    "last": round(price, 2),
                    "open_interest": 500,
                    "implied_vol": IV,
                    "ts": TS,
                })
    return {"underlyings": {"SPY": {"price": SPOT, "ts": TS}}, "chains": {"SPY": rows}}


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_market.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(f"wrote {out}")
