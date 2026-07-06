"""The Phase-1 pipeline — one deterministic pass, wiring every module together.

    market data -> analytics -> store feature + IV history -> build -> save + publish

This is the seam the scheduler drives on a loop and the backtester replays. Appending
each pass's ATM IV to the history store is what turns IV rank from neutral (50) into a
real, ranked number over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from paz_rav.analytics import analyze
from paz_rav.builder import build
from paz_rav.bus import CH_CANDIDATES, CH_FEATURES
from paz_rav.contracts import Feature
from paz_rav.positions.base import Position
from paz_rav.positions.exit_manager import sweep as sweep_exits
from paz_rav.store.serialize import candidate_to_dict
from paz_rav.strategies import BuildConfig, Candidate, MarketContext


@dataclass(frozen=True, slots=True)
class ScanResult:
    feature: Feature
    candidates: list[Candidate]
    flagged_positions: list[Position] | None = None   # newly alerted this scan (advisory)


class Pipeline:
    """Holds the wiring; ``run_once`` executes one full deterministic scan."""

    def __init__(self, md, feature_store, iv_history, candidate_repo, bus,
                 config: BuildConfig | None = None, strategies: list[str] | None = None,
                 position_repo=None):
        self.md = md
        self.feature_store = feature_store
        self.iv_history = iv_history
        self.candidate_repo = candidate_repo
        self.bus = bus
        self.config = config or BuildConfig()
        self.strategies = strategies   # None => all registered
        self.position_repo = position_repo   # None => Phase-3 exit sweep skipped

    async def run_once(self, underlying: str, *, today: date | None = None) -> ScanResult | None:
        today = today or date.today()

        spot = (await self.md.underlying(underlying)).price
        expiries = sorted(await self.md.list_expiries(underlying))
        if not expiries:
            return None

        # Fetch expiries a month apart: iron condor uses the front, DACS needs both.
        targets = (self.config.dacs_short_dte,
                   self.config.dacs_short_dte + self.config.dacs_gap_days)
        chosen: list[date] = []
        for tgt in targets:
            e = min(expiries, key=lambda e: abs((e - today).days - tgt))
            if e not in chosen:
                chosen.append(e)
        chains = {e: await self.md.chain(underlying, e) for e in chosen}

        # optional trend input, if the feed can supply recent closes (duck-typed)
        price_history = None
        if hasattr(self.md, "recent_closes"):
            try:
                price_history = await self.md.recent_closes(underlying, 30)
            except Exception:
                price_history = None

        # optional earnings check (DACS must avoid earnings within ~2 weeks)
        earnings_soon = False
        if hasattr(self.md, "earnings_within"):
            try:
                earnings_soon = await self.md.earnings_within(underlying, 14)
            except Exception:
                earnings_soon = False

        iv_hist = await self.iv_history.window(underlying, 365)
        result = analyze(
            underlying, spot=spot, chains_by_expiry=chains,
            iv_history=iv_hist or None, price_history=price_history, today=today,
        )

        # persist + publish features; record IV so future IV rank is real
        await self.feature_store.put(result.feature)
        await self.iv_history.append(underlying, result.atm_iv, result.feature.ts)
        await self.bus.publish(CH_FEATURES, result.feature.model_dump(mode="json"))

        ctx = MarketContext(regime=result.feature.regime, iv_rank=result.feature.iv_rank,
                            term_slope=result.feature.term_slope, rsi=result.feature.rsi,
                            earnings_soon=earnings_soon)
        candidates = build(underlying, spot=spot, chains_by_expiry=chains,
                           config=self.config, ctx=ctx, today=today,
                           strategies=self.strategies)
        await self.candidate_repo.save(candidates)
        await self.bus.publish(CH_CANDIDATES, {
            "underlying": underlying,
            "candidates": [candidate_to_dict(c) for c in candidates],
        })

        flagged = None
        if self.position_repo is not None:
            flagged = await sweep_exits(self.position_repo, underlying, spot, today)

        return ScanResult(feature=result.feature, candidates=candidates, flagged_positions=flagged)
