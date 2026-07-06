"""Diagonal — one-sided calendar with a strike offset (call or put).

Sell a front-month option, buy a further-OTM back-month option on the same side. Long
vega like the double diagonal; a lighter, directional cousin. Enumerates both a call
diagonal and a put diagonal and lets the shared score rank them.
"""

from __future__ import annotations

from datetime import date

from paz_rav.strategies.base import AnnotatedQuote, BuildConfig, Candidate, Leg, MarketContext
from paz_rav.strategies.double_diagonal import _by_expiry, _nearest, _pick_expiries
from paz_rav.strategies.scoring import calendar_fit, finalize


class Diagonal:
    name = "diagonal"

    def enumerate(
        self, *, underlying: str, spot: float, chain: list[AnnotatedQuote],
        config: BuildConfig, today: date, ctx: MarketContext,
    ) -> list[Candidate]:
        front, back = _pick_expiries(chain, config.target_dte)
        if front is None:
            return []
        by = _by_expiry(chain)
        fq, bq = by[front], by[back]

        def liquid(q: AnnotatedQuote) -> bool:
            return (q.mid > 0 and q.open_interest >= config.min_open_interest
                    and q.rel_spread <= config.max_rel_spread)

        fit = calendar_fit(ctx)
        out: list[Candidate] = []

        for right in ("call", "put"):
            front_side = [q for q in fq if q.right == right]
            back_side = [q for q in bq if q.right == right]
            if not front_side or not back_side:
                continue
            for short_delta in config.short_deltas:
                target = short_delta / 100.0
                short = min(front_side, key=lambda q: abs(abs(q.delta) - target), default=None)
                if short is None:
                    continue
                for wing in config.wing_widths:
                    # long leg further OTM: higher strike for calls, lower for puts
                    long_strike = short.strike + wing if right == "call" else short.strike - wing
                    long_q = _nearest(back_side, long_strike)
                    if long_q is None or not liquid(short) or not liquid(long_q):
                        continue
                    entry = short.mid - long_q.mid
                    legs = [
                        Leg("sell", right, short.strike, expiry=front, iv=short.iv),
                        Leg("buy", right, long_q.strike, expiry=back, iv=long_q.iv),
                    ]
                    c = finalize(
                        underlying=underlying, strategy=f"{self.name}_{right}", legs=legs,
                        entry_credit=entry, spot=spot, eval_date=front,
                        sigma=short.iv or 0.20, today=today, regime_fit=fit, width=wing,
                        vrp=config.vrp,
                    )
                    if c.max_loss > 1e-6:
                        out.append(c)

        out.sort(key=lambda c: c.score, reverse=True)
        return out[: config.top_n]
