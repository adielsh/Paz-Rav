"""DACS 1.0 — Diagonal Adaptive Calendar Spread (call side).

The rules, encoded:
  * Sell a CALL ~1 month out, ~8-10% OTM, delta <= 0.20.
  * Buy a CALL ~1 month beyond the short at the same strike, for a small net DEBIT, with
    the long worth > $1 (a debit spread keeps margin low and the trade conservative).
  * Fast ratio = long value / capital at risk; skip if below a floor (~12%).
  * Timing (via regime fit): stable name, RSI ~60, LOW IV, and NO earnings within ~2 wks.
If the name doesn't move, the short decays away and you sell the long for the profit.
Stop levels (short strike -1 aggressive .. -5 conservative) ride along in ``meta``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from paz_rav.strategies.base import AnnotatedQuote, BuildConfig, Candidate, Leg, MarketContext
from paz_rav.strategies.double_diagonal import _by_expiry
from paz_rav.strategies.scoring import dacs_fit, finalize


class DACS:
    name = "dacs"

    def enumerate(
        self, *, underlying: str, spot: float, chain: list[AnnotatedQuote],
        config: BuildConfig, today: date, ctx: MarketContext,
    ) -> list[Candidate]:
        by = _by_expiry(chain)
        if len(by) < 2:
            return []
        dtes = {e: qs[0].dte for e, qs in by.items()}
        short_exp = min(dtes, key=lambda e: abs(dtes[e] - config.dacs_short_dte))
        later = [e for e in dtes if dtes[e] > dtes[short_exp]]
        if not later:
            return []
        long_target = dtes[short_exp] + config.dacs_gap_days
        long_exp = min(later, key=lambda e: abs(dtes[e] - long_target))

        short_calls = [q for q in by[short_exp] if q.right == "call"]
        long_calls = [q for q in by[long_exp] if q.right == "call"]
        if not short_calls or not long_calls:
            return []

        def liquid(q: AnnotatedQuote) -> bool:
            return (q.mid > 0 and q.open_interest >= config.min_open_interest
                    and q.rel_spread <= config.max_rel_spread)

        # short: ~10% OTM call with delta <= cap
        min_strike = spot * (1 + config.dacs_otm * 0.8)   # at least ~8% OTM
        eligible = [q for q in short_calls
                    if q.delta <= config.dacs_max_delta and q.strike >= min_strike and liquid(q)]
        if not eligible:
            return []
        target_strike = spot * (1 + config.dacs_otm)
        short = min(eligible, key=lambda q: abs(q.strike - target_strike))

        # long: same strike, one month further out, worth > $1
        long = min(long_calls, key=lambda q: abs(q.strike - short.strike))
        if not liquid(long) or long.mid < config.dacs_min_long_price:
            return []

        entry = short.mid - long.mid   # negative => small debit paid
        legs = [
            Leg("sell", "call", short.strike, expiry=short_exp, iv=short.iv, delta=short.delta),
            Leg("buy", "call", long.strike, expiry=long_exp, iv=long.iv, delta=long.delta),
        ]
        c = finalize(
            underlying=underlying, strategy=self.name, legs=legs, entry_credit=entry,
            spot=spot, eval_date=short_exp, sigma=short.iv or 0.20, today=today,
            regime_fit=dacs_fit(ctx), width=abs(long.strike - short.strike), vrp=config.vrp,
        )
        if c.max_loss <= 1e-6:
            return []
        fast_ratio = round(long.mid / c.max_loss, 3)
        if fast_ratio < config.dacs_min_fast_ratio:
            return []

        c = replace(c, meta={
            **c.meta,
            "fast_ratio": fast_ratio,
            "stop_aggressive": round(short.strike - 1, 2),
            "stop_conservative": round(short.strike - 5, 2),
            "short_expiry": short_exp.isoformat(),
            "long_expiry": long_exp.isoformat(),
            "otm_pct": round((short.strike / spot - 1) * 100, 1),
            "long_debit": round(-entry, 2) if entry < 0 else 0.0,
        })
        return [c]
