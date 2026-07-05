"""Iron condor — the core premium-selling structure.

Sell an out-of-the-money put spread and call spread for a net credit; profit if the
underlying stays between the short strikes. Defined risk = wing width - credit.
"""

from __future__ import annotations

from paz_rav.quant.pop import prob_of_profit
from paz_rav.strategies.base import AnnotatedQuote, BuildConfig, Candidate, Leg


class IronCondor:
    name = "iron_condor"

    def enumerate(
        self, *, underlying: str, spot: float, dte: int,
        chain: list[AnnotatedQuote], config: BuildConfig,
    ) -> list[Candidate]:
        """Build ranked condors: short strikes at target deltas, wings at target widths.

        For each (short delta, wing width) pair we pick the short put/call nearest that
        delta, place the long wings, apply liquidity filters, and price the structure.
        Results are de-duplicated by strikes and sorted best-score first.
        """
        puts = sorted((q for q in chain if q.right == "put"), key=lambda q: q.strike)
        calls = sorted((q for q in chain if q.right == "call"), key=lambda q: q.strike)
        if not puts or not calls:
            return []

        def liquid(q: AnnotatedQuote) -> bool:
            return (
                q.mid > 0
                and q.open_interest >= config.min_open_interest
                and 0 < q.rel_spread <= config.max_rel_spread
            )

        seen: set[tuple[float, float, float, float]] = set()
        candidates: list[Candidate] = []

        for short_delta in config.short_deltas:
            target = short_delta / 100.0
            short_put = min((q for q in puts if q.delta < 0),
                            key=lambda q: abs(abs(q.delta) - target), default=None)
            short_call = min((q for q in calls if q.delta > 0),
                             key=lambda q: abs(q.delta - target), default=None)
            if short_put is None or short_call is None:
                continue

            for width in config.wing_widths:
                long_put = min(puts, key=lambda q: abs(q.strike - (short_put.strike - width)))
                long_call = min(calls, key=lambda q: abs(q.strike - (short_call.strike + width)))
                legs = (long_put, short_put, short_call, long_call)

                if not (long_put.strike < short_put.strike < short_call.strike < long_call.strike):
                    continue
                if not all(liquid(q) for q in legs):
                    continue

                key = (long_put.strike, short_put.strike, short_call.strike, long_call.strike)
                if key in seen:
                    continue
                seen.add(key)

                credit = short_put.mid - long_put.mid + short_call.mid - long_call.mid
                if credit <= 0:
                    continue

                try:
                    candidates.append(self.build(
                        underlying=underlying, spot=spot, dte=dte,
                        put_long=long_put.strike, put_short=short_put.strike,
                        call_short=short_call.strike, call_long=long_call.strike,
                        credit=round(credit, 2), sigma=short_put.iv or 0.20,
                    ))
                except ValueError:
                    continue

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[: config.top_n]

    def build(
        self,
        *,
        underlying: str,
        spot: float,
        dte: int,
        put_long: float,
        put_short: float,
        call_short: float,
        call_long: float,
        credit: float,
        sigma: float,
    ) -> Candidate:
        """Assemble a priced iron condor from its four strikes and the net credit.

        Strikes must satisfy ``put_long < put_short < spot < call_short < call_long``.
        ``credit`` and strikes are in the same per-share dollar units.
        """
        if not (put_long < put_short < call_short < call_long):
            raise ValueError("strikes must be ordered put_long < put_short < call_short < call_long")
        if credit <= 0:
            raise ValueError("iron condor must be opened for a net credit")

        put_width = put_short - put_long
        call_width = call_long - call_short
        width = max(put_width, call_width)  # margin is set by the wider spread

        legs = (
            Leg("buy", "put", put_long),
            Leg("sell", "put", put_short),
            Leg("sell", "call", call_short),
            Leg("buy", "call", call_long),
        )
        max_profit = credit
        max_loss = width - credit
        breakevens = (put_short - credit, call_short + credit)

        t = dte / 365.0
        pop = prob_of_profit(spot, breakevens, sigma, t, profit_region="between")

        c = Candidate(
            underlying=underlying,
            strategy=self.name,
            dte=dte,
            legs=legs,
            credit=credit,
            width=width,
            max_profit=max_profit,
            max_loss=max_loss,
            breakevens=breakevens,
            pop=pop,
        )
        # Candidate is frozen; stamp the score by rebuilding with it filled in.
        return _with_score(c, self.score(c))

    def score(self, c: Candidate) -> float:
        """Rank by credit-to-width tilted by probability of profit.

        A clean, explainable proxy: reward richer premium per dollar of risk, weighted
        by how likely the trade is to win. Real ranking later folds in greeks/liquidity.
        """
        if c.width <= 0:
            return 0.0
        credit_to_width = c.credit / c.width
        return round(credit_to_width * c.pop, 6)


def _with_score(c: Candidate, score: float) -> Candidate:
    from dataclasses import replace

    return replace(c, score=score)
