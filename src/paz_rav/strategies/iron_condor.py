"""Iron condor — the core premium-selling structure.

Sell an OTM put spread and call spread for a net credit; profit if the underlying stays
between the short strikes. Single expiry, defined risk = wing width - credit. Loves
range-bound + high-IV regimes.
"""

from __future__ import annotations

from datetime import date, timedelta

from paz_rav.strategies.base import AnnotatedQuote, BuildConfig, Candidate, Leg, MarketContext
from paz_rav.strategies.scoring import condor_fit, finalize


def _front_expiry(chain: list[AnnotatedQuote], target_dte: int):
    """The expiry in the chain whose DTE is nearest the target."""
    expiries = {q.expiry: q.dte for q in chain}
    if not expiries:
        return None
    return min(expiries, key=lambda e: abs(expiries[e] - target_dte))


class IronCondor:
    name = "iron_condor"

    def build(
        self, *, underlying: str, spot: float, dte: int,
        put_long: float, put_short: float, call_short: float, call_long: float,
        credit: float, sigma: float,
        today: date | None = None, ctx: MarketContext | None = None, vrp: float = 0.0,
        deltas: tuple[float | None, float | None, float | None, float | None] = (None,) * 4,
    ) -> Candidate:
        """Assemble a priced iron condor from its four strikes and the net credit.

        ``deltas`` (optional) are the scan-time leg deltas in strike order
        (put_long, put_short, call_short, call_long) — shown per leg on the dashboard.
        """
        if not (put_long < put_short < call_short < call_long):
            raise ValueError("strikes must be ordered put_long < put_short < call_short < call_long")
        if credit <= 0:
            raise ValueError("iron condor must be opened for a net credit")

        today = today or date.today()
        eval_date = today + timedelta(days=max(dte, 1))
        width = max(put_short - put_long, call_long - call_short)  # margin = wider spread

        d_lp, d_sp, d_sc, d_lc = deltas
        legs = [
            Leg("buy", "put", put_long, expiry=eval_date, delta=d_lp),
            Leg("sell", "put", put_short, expiry=eval_date, delta=d_sp),
            Leg("sell", "call", call_short, expiry=eval_date, delta=d_sc),
            Leg("buy", "call", call_long, expiry=eval_date, delta=d_lc),
        ]
        return finalize(
            underlying=underlying, strategy=self.name, legs=legs, entry_credit=credit,
            spot=spot, eval_date=eval_date, sigma=sigma, today=today, vrp=vrp,
            regime_fit=condor_fit(ctx or MarketContext()), width=width,
            max_profit=credit, max_loss=width - credit,
            breakevens=(put_short - credit, call_short + credit),
        )

    def enumerate(
        self, *, underlying: str, spot: float, chain: list[AnnotatedQuote],
        config: BuildConfig, today: date, ctx: MarketContext,
    ) -> list[Candidate]:
        """Build ranked condors from the expiry nearest the target DTE."""
        front = _front_expiry(chain, config.target_dte)
        if front is None:
            return []
        quotes = [q for q in chain if q.expiry == front]
        dte = next(q.dte for q in quotes)
        puts = sorted((q for q in quotes if q.right == "put"), key=lambda q: q.strike)
        calls = sorted((q for q in quotes if q.right == "call"), key=lambda q: q.strike)
        if not puts or not calls:
            return []

        def liquid(q: AnnotatedQuote) -> bool:
            return (q.mid > 0 and q.open_interest >= config.min_open_interest
                    and q.rel_spread <= config.max_rel_spread)

        seen: set[tuple[float, float, float, float]] = set()
        out: list[Candidate] = []
        for short_delta in config.short_deltas:
            target = short_delta / 100.0
            sp = min((q for q in puts if q.delta < 0),
                     key=lambda q: abs(abs(q.delta) - target), default=None)
            sc = min((q for q in calls if q.delta > 0),
                     key=lambda q: abs(q.delta - target), default=None)
            if sp is None or sc is None:
                continue
            # The nearest strike must actually BE near the target delta. On a broken chain
            # (stale/one-sided closed-market quotes) every delta collapses toward 0, the
            # "closest to 16Δ" short ends up at 0.0002Δ, POP looks like ~1.0, and one random
            # name floods the rankings. No honest short near target -> no trade, full stop.
            if (abs(abs(sp.delta) - target) > config.short_delta_tolerance
                    or abs(sc.delta - target) > config.short_delta_tolerance):
                continue
            if not (liquid(sp) and liquid(sc)):
                continue
            # Equal-width wings on BOTH sides, by construction. Strike spacing often differs
            # between the put and call regions (e.g. SPX: 25-wide near the puts, 100-wide
            # near the calls), so "k strikes out" on each side yields lopsided wings. The
            # collateral is set by the *wider* spread either way — and price can't breach
            # both sides at once — so the narrower side should always be widened to match:
            # same margin, more premium collected. We therefore intersect the wing widths
            # actually available (as liquid strikes) on both sides and use the k-th
            # smallest COMMON width — wings come out exactly equal on any grid.
            put_widths = {round(sp.strike - q.strike, 4): q
                          for q in puts if q.strike < sp.strike and liquid(q)}
            call_widths = {round(q.strike - sc.strike, 4): q
                           for q in calls if q.strike > sc.strike and liquid(q)}
            common = sorted(set(put_widths) & set(call_widths))
            for k in config.wing_strikes:
                if k - 1 >= len(common):
                    continue
                width_k = common[k - 1]
                lp, lc = put_widths[width_k], call_widths[width_k]
                key = (lp.strike, sp.strike, sc.strike, lc.strike)
                if key in seen:
                    continue
                seen.add(key)
                credit = sp.mid - lp.mid + sc.mid - lc.mid
                if credit <= 0:
                    continue
                try:
                    out.append(self.build(
                        underlying=underlying, spot=spot, dte=dte,
                        put_long=lp.strike, put_short=sp.strike,
                        call_short=sc.strike, call_long=lc.strike,
                        credit=round(credit, 2), sigma=sp.iv or 0.20,
                        today=today, ctx=ctx, vrp=config.vrp,
                        deltas=(lp.delta, sp.delta, sc.delta, lc.delta),
                    ))
                except ValueError:
                    continue

        # POP ~1.0 isn't free money — it's degenerate pricing from bad inputs. Reject it.
        out = [c for c in out if c.pop <= config.max_pop]
        out.sort(key=lambda c: c.score, reverse=True)
        return out[: config.top_n]
