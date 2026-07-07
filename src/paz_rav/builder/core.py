"""Builder — annotate the chain with greeks, then enumerate & rank ALL strategies.

The builder computes the delta/IV/liquidity each strategy needs, hands every registered
strategy the same annotated (multi-expiry) chain, and merges their candidates into one
score-ranked list. Iron condor, double diagonal and diagonal compete head-to-head.
Adding a strategy never touches this file (Strategy + Factory).
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
    MarketContext,
    list_strategies,
    make_strategy,
)


def annotate(
    quotes: list[OptionQuote], spot: float, config: BuildConfig,
    *, iv_fallback: float = 0.20, today: date | None = None,
) -> list[AnnotatedQuote]:
    """Enrich each quote with delta, IV, DTE and a liquidity measure (computes greeks)."""
    today = today or date.today()
    out: list[AnnotatedQuote] = []
    for q in quotes:
        # Off-hours the bid/ask are often 0; fall back to last so the chain stays usable.
        mid = q.mid if q.mid > 0 else (q.last or 0.0)
        if mid <= 0:
            continue
        dte = max((q.expiry - today).days, 0)
        t = max(dte, 1) / 365.0
        # No vendor IV and the solver can't price it either -> the quote is broken (stale
        # last, one-sided book); inventing a fallback vol here is how garbage used to enter
        # the chain. Same for a solved IV outside the sane band: greeks/POP computed from
        # it would be fiction (deltas ~0, POP ~1.0), so the quote is dropped, not "fixed".
        iv = contract_iv(q, spot, config.r, today)
        if iv is None or not (config.min_iv <= iv <= config.max_iv):
            continue
        try:
            delta = greeks(spot, q.strike, t, config.r, iv, q.right).delta
        except ValueError:
            continue
        # rel_spread only meaningful with a 2-sided market; 0 = "unknown" (not rejected).
        rel_spread = (q.ask - q.bid) / mid if (q.bid > 0 and q.ask > 0) else 0.0
        out.append(AnnotatedQuote(
            right=q.right, strike=q.strike, mid=mid, delta=delta, iv=iv,
            open_interest=q.open_interest or 0, rel_spread=rel_spread,
            expiry=q.expiry, dte=dte,
        ))
    return out


def build(
    underlying: str, spot: float, chains_by_expiry: dict[date, list[OptionQuote]],
    config: BuildConfig | None = None, *, ctx: MarketContext | None = None,
    strategies: list[str] | None = None, iv_fallback: float = 0.20,
    today: date | None = None,
) -> list[Candidate]:
    """Full builder pass across expiries and strategies; returns the top-ranked set."""
    config = config or BuildConfig()
    ctx = ctx or MarketContext()
    today = today or date.today()

    chain: list[AnnotatedQuote] = []
    for quotes in chains_by_expiry.values():
        chain.extend(annotate(quotes, spot, config, iv_fallback=iv_fallback, today=today))

    names = strategies if strategies is not None else list_strategies()
    all_candidates: list[Candidate] = []
    for name in names:
        strat = make_strategy(name)
        all_candidates.extend(strat.enumerate(
            underlying=underlying, spot=spot, chain=chain, config=config,
            today=today, ctx=ctx,
        ))

    all_candidates.sort(key=lambda c: c.score, reverse=True)
    return all_candidates[: config.top_n]
