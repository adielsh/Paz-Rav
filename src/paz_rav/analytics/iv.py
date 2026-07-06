"""IV extraction and IV-rank helpers — the vol side of the feature engine."""

from __future__ import annotations

from datetime import date

from paz_rav.contracts import OptionQuote
from paz_rav.quant.implied_vol import implied_vol


def contract_iv(q: OptionQuote, spot: float, r: float = 0.04, today: date | None = None) -> float | None:
    """Best available implied vol for one contract: vendor's if present, else solved."""
    if q.implied_vol and q.implied_vol > 0:
        return q.implied_vol
    price = q.mid
    if price <= 0:
        return None
    today = today or date.today()
    t = max((q.expiry - today).days, 1) / 365.0
    try:
        return implied_vol(price, spot, q.strike, t, r, q.right)
    except ValueError:
        return None


def _nearest(quotes: list[OptionQuote], right: str, spot: float) -> OptionQuote | None:
    side = [q for q in quotes if q.right == right]
    return min(side, key=lambda q: abs(q.strike - spot)) if side else None


def atm_iv(quotes: list[OptionQuote], spot: float, r: float = 0.04, today: date | None = None) -> float | None:
    """At-the-money implied vol: average of the nearest call and put IVs."""
    ivs = []
    for right in ("call", "put"):
        q = _nearest(quotes, right, spot)
        if q is not None:
            v = contract_iv(q, spot, r, today)
            if v is not None:
                ivs.append(v)
    return sum(ivs) / len(ivs) if ivs else None


def skew(quotes: list[OptionQuote], spot: float, r: float = 0.04, moneyness: float = 0.05,
         today: date | None = None) -> float:
    """OTM put IV minus OTM call IV at symmetric moneyness (put skew is usually positive)."""
    put = _nearest(quotes, "put", spot * (1 - moneyness))
    call = _nearest(quotes, "call", spot * (1 + moneyness))
    pv = contract_iv(put, spot, r, today) if put else None
    cv = contract_iv(call, spot, r, today) if call else None
    if pv is None or cv is None:
        return 0.0
    return pv - cv


def iv_rank(current: float, history: list[float]) -> float:
    """Where current IV sits in its 1-year [min, max] range, 0..100."""
    if not history:
        return 50.0  # unknown → neutral
    lo, hi = min(history), max(history)
    if hi <= lo:
        return 50.0
    return max(0.0, min(100.0, (current - lo) / (hi - lo) * 100.0))


def iv_percentile(current: float, history: list[float]) -> float:
    """Percent of history strictly below current IV, 0..100."""
    if not history:
        return 50.0
    below = sum(1 for v in history if v < current)
    return 100.0 * below / len(history)
