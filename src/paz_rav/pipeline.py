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
from paz_rav.store.serialize import candidate_to_dict
from paz_rav.strategies import BuildConfig, Candidate


@dataclass(frozen=True, slots=True)
class ScanResult:
    feature: Feature
    candidates: list[Candidate]


class Pipeline:
    """Holds the wiring; ``run_once`` executes one full deterministic scan."""

    def __init__(self, md, feature_store, iv_history, candidate_repo, bus,
                 config: BuildConfig | None = None):
        self.md = md
        self.feature_store = feature_store
        self.iv_history = iv_history
        self.candidate_repo = candidate_repo
        self.bus = bus
        self.config = config or BuildConfig()

    async def run_once(self, underlying: str, *, today: date | None = None) -> ScanResult | None:
        today = today or date.today()
        target = self.config.target_dte

        spot = (await self.md.underlying(underlying)).price
        expiries = sorted(await self.md.list_expiries(underlying))
        if not expiries:
            return None

        # front expiry nearest the target DTE, plus the next one for the term slope
        front = min(expiries, key=lambda e: abs((e - today).days - target))
        idx = expiries.index(front)
        back = expiries[min(idx + 1, len(expiries) - 1)]

        chains = {front: await self.md.chain(underlying, front)}
        if back != front:
            chains[back] = await self.md.chain(underlying, back)

        # optional trend input, if the feed can supply recent closes (duck-typed)
        price_history = None
        if hasattr(self.md, "recent_closes"):
            try:
                price_history = await self.md.recent_closes(underlying, 20)
            except Exception:
                price_history = None

        iv_hist = await self.iv_history.window(underlying, 365)
        result = analyze(
            underlying, spot=spot, chains_by_expiry=chains,
            iv_history=iv_hist or None, price_history=price_history, today=today,
        )

        # persist + publish features; record IV so future IV rank is real
        await self.feature_store.put(result.feature)
        await self.iv_history.append(underlying, result.atm_iv, result.feature.ts)
        await self.bus.publish(CH_FEATURES, result.feature.model_dump(mode="json"))

        dte = (front - today).days
        candidates = build(underlying, spot=spot, dte=dte, quotes=chains[front],
                           config=self.config, today=today)
        await self.candidate_repo.save(candidates)
        await self.bus.publish(CH_CANDIDATES, {
            "underlying": underlying,
            "candidates": [candidate_to_dict(c) for c in candidates],
        })

        return ScanResult(feature=result.feature, candidates=candidates)
