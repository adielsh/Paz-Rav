"""Double diagonal — sell a front-month strangle, buy a back-month wider strangle.

Two diagonals at once (put side + call side). The short front legs decay fast; the long
back legs are still alive at the front expiry and are *priced* by the grid. Net usually a
debit; profits when the underlying sits in a range through the front expiry, and it is
long vega — so it prefers range-bound + LOW IV (buy vol cheap), the opposite regime to
an iron condor. That complementarity is why the global ranker can always surface a fit.
"""

from __future__ import annotations

from datetime import date

from paz_rav.strategies.base import AnnotatedQuote, BuildConfig, Candidate, Leg, MarketContext
from paz_rav.strategies.scoring import calendar_fit, finalize


def _by_expiry(chain: list[AnnotatedQuote]) -> dict[date, list[AnnotatedQuote]]:
    out: dict[date, list[AnnotatedQuote]] = {}
    for q in chain:
        out.setdefault(q.expiry, []).append(q)
    return out


def _pick_expiries(chain: list[AnnotatedQuote], target_dte: int):
    by = _by_expiry(chain)
    if len(by) < 2:
        return None, None
    dtes = {e: qs[0].dte for e, qs in by.items()}
    front = min(dtes, key=lambda e: abs(dtes[e] - target_dte))
    later = [e for e in dtes if dtes[e] > dtes[front]]
    if not later:
        return None, None
    back = min(later, key=lambda e: dtes[e])   # nearest longer-dated expiry
    return front, back


def _nearest(quotes: list[AnnotatedQuote], strike: float) -> AnnotatedQuote | None:
    return min(quotes, key=lambda q: abs(q.strike - strike)) if quotes else None


class DoubleDiagonal:
    name = "double_diagonal"

    def enumerate(
        self, *, underlying: str, spot: float, chain: list[AnnotatedQuote],
        config: BuildConfig, today: date, ctx: MarketContext,
    ) -> list[Candidate]:
        front, back = _pick_expiries(chain, config.target_dte)
        if front is None:
            return []
        by = _by_expiry(chain)
        fq, bq = by[front], by[back]
        front_puts = [q for q in fq if q.right == "put"]
        front_calls = [q for q in fq if q.right == "call"]
        back_puts = [q for q in bq if q.right == "put"]
        back_calls = [q for q in bq if q.right == "call"]
        if not (front_puts and front_calls and back_puts and back_calls):
            return []

        def liquid(q: AnnotatedQuote) -> bool:
            return (q.mid > 0 and q.open_interest >= config.min_open_interest
                    and q.rel_spread <= config.max_rel_spread)

        fit = calendar_fit(ctx)
        out: list[Candidate] = []
        seen: set = set()

        for short_delta in config.short_deltas:
            target = short_delta / 100.0
            sp = min((q for q in front_puts if q.delta < 0),
                     key=lambda q: abs(abs(q.delta) - target), default=None)
            sc = min((q for q in front_calls if q.delta > 0),
                     key=lambda q: abs(q.delta - target), default=None)
            if sp is None or sc is None:
                continue
            for wing in config.wing_widths:
                lp = _nearest(back_puts, sp.strike - wing)    # long put further OTM, back month
                lc = _nearest(back_calls, sc.strike + wing)   # long call further OTM, back month
                if lp is None or lc is None:
                    continue
                if not (lp.strike < sp.strike < sc.strike < lc.strike):
                    continue
                legs_q = (sp, sc, lp, lc)
                if not all(liquid(q) for q in legs_q):
                    continue
                key = (sp.strike, sc.strike, lp.strike, lc.strike)
                if key in seen:
                    continue
                seen.add(key)

                # net credit (negative => debit paid for the longer-dated protection)
                entry = sp.mid + sc.mid - lp.mid - lc.mid
                legs = [
                    Leg("sell", "put", sp.strike, expiry=front, iv=sp.iv),
                    Leg("sell", "call", sc.strike, expiry=front, iv=sc.iv),
                    Leg("buy", "put", lp.strike, expiry=back, iv=lp.iv),
                    Leg("buy", "call", lc.strike, expiry=back, iv=lc.iv),
                ]
                c = finalize(
                    underlying=underlying, strategy=self.name, legs=legs, entry_credit=entry,
                    spot=spot, eval_date=front, sigma=sp.iv or 0.20, today=today,
                    regime_fit=fit, width=wing,
                )
                if c.max_loss > 1e-6:      # keep only well-defined-risk candidates
                    out.append(c)

        out.sort(key=lambda c: c.score, reverse=True)
        return out[: config.top_n]
