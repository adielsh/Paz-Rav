"""The feature engine — turns raw chains into the one Feature everything reasons over.

`analyze()` is deterministic: same inputs, same output. It is the seam where the live
pipeline and the backtester meet (both call it), guaranteeing one code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from paz_rav.analytics import iv as ivmod
from paz_rav.analytics import regime as regimemod
from paz_rav.analytics.rsi import rsi as compute_rsi
from paz_rav.contracts import Feature, OptionQuote
from paz_rav.quant.pop import expected_move


@dataclass(frozen=True, slots=True)
class AnalyticsResult:
    """The Feature plus the richer numbers the UI and builder want."""

    feature: Feature
    atm_iv: float
    skew: float
    per_expiry_iv: dict[str, float] = field(default_factory=dict)
    condor_friendly: bool = False


def analyze(
    underlying: str,
    spot: float,
    chains_by_expiry: dict[date, list[OptionQuote]],
    *,
    iv_history: list[float] | None = None,
    price_history: list[float] | None = None,
    r: float = 0.04,
    today: date | None = None,
    ts: datetime | None = None,
) -> AnalyticsResult:
    """Compute per-underlying features from one or more expiries' chains."""
    if not chains_by_expiry:
        raise ValueError("no chains provided")
    today = today or date.today()
    ts = ts or datetime.now(timezone.utc)

    expiries = sorted(chains_by_expiry)
    front = expiries[0]
    front_quotes = chains_by_expiry[front]
    t_front = max((front - today).days, 1) / 365.0

    atm_front = ivmod.atm_iv(front_quotes, spot, r, today) or 0.20
    em = expected_move(spot, atm_front, t_front)
    sk = ivmod.skew(front_quotes, spot, r, today=today)

    per_expiry_iv: dict[str, float] = {}
    for e in expiries:
        v = ivmod.atm_iv(chains_by_expiry[e], spot, r, today)
        if v is not None:
            per_expiry_iv[e.isoformat()] = round(v, 4)

    # Term-structure slope: back-month ATM IV minus front, per year of extra tenor.
    term_slope = 0.0
    if len(expiries) >= 2:
        back = expiries[1]
        atm_back = ivmod.atm_iv(chains_by_expiry[back], spot, r, today) or atm_front
        t_back = max((back - today).days, 1) / 365.0
        term_slope = (atm_back - atm_front) / max(t_back - t_front, 1e-6)

    ivr = ivmod.iv_rank(atm_front, iv_history) if iv_history else 50.0
    regime = regimemod.classify(ivr, spot, price_history)
    rsi_val = compute_rsi(price_history) if price_history else None

    feature = Feature(
        underlying=underlying,
        spot=spot,
        iv_rank=round(ivr, 2),
        term_slope=round(term_slope, 5),
        expected_move=round(em, 4),
        regime=regime,
        rsi=rsi_val,
        ts=ts,
    )
    return AnalyticsResult(
        feature=feature,
        atm_iv=round(atm_front, 4),
        skew=round(sk, 4),
        per_expiry_iv=per_expiry_iv,
        condor_friendly=regimemod.condor_friendly(regime),
    )
