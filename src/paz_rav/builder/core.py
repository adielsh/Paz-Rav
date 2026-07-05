"""Builder — annotate a chain with greeks, then enumerate & rank candidates.

The builder does not know how any structure is built; it computes the delta/IV/liquidity
each strategy needs, then asks every registered strategy to ``enumerate``. Adding a
strategy never touches this file (Strategy + Factory patterns).
"""

from __future__ import annotations

from datetime import date

from paz_rav.analytics.iv import contract_iv
from paz_rav.contracts import OptionQuote
from paz_rav.quant.greeks import greeks
from paz_rav.strategies import (
    AnnotatedQuote,
    BuildConfig,
    Candidate,
    OptionStrategy,
    list_strategies,
    make_strategy,
)


def annotate(
    quotes: list[OptionQuote], spot: float, config: BuildConfig,
    *, iv_fallback: float = 0.20, today: date | None = None,
) -> list[AnnotatedQuote]:
    """Enrich each quote with delta, IV and a liquidity measure (computes greeks)."""
    today = today or date.today()
    out: list[AnnotatedQuote] = []
    for q in quotes:
        mid = q.mid
        if mid <= 0:
            continue
        t = max((q.expiry - today).days, 1) / 365.0
        iv = contract_iv(q, spot, config.r, today) or iv_fallback
        try:
            delta = greeks(spot, q.strike, t, config.r, iv, q.right).delta
        except ValueError:
            continue
        rel_spread = (q.ask - q.bid) / mid if mid > 0 else float("inf")
        out.append(AnnotatedQuote(
            right=q.right, strike=q.strike, mid=mid, delta=delta, iv=iv,
            open_interest=q.open_interest or 0, rel_spread=rel_spread,
        ))
    return out


def build(
    underlying: str, spot: float, dte: int, quotes: list[OptionQuote],
    config: BuildConfig | None = None,
    *, strategies: list[str] | None = None, iv_fallback: float = 0.20,
    today: date | None = None,
) -> list[Candidate]:
    """Full builder pass: annotate, run each strategy's enumeration, merge & rank."""
    config = config or BuildConfig()
    chain = annotate(quotes, spot, config, iv_fallback=iv_fallback, today=today)

    names = strategies if strategies is not None else list_strategies()
    all_candidates: list[Candidate] = []
    for name in names:
        strat: OptionStrategy = make_strategy(name)
        all_candidates.extend(strat.enumerate(
            underlying=underlying, spot=spot, dte=dte, chain=chain, config=config,
        ))

    all_candidates.sort(key=lambda c: c.score, reverse=True)
    return all_candidates[: config.top_n]
