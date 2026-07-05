"""In-memory stores — for tests and offline dev. Zero infrastructure."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate


class InMemoryFeatureStore:
    def __init__(self) -> None:
        self._d: dict[str, Feature] = {}

    async def put(self, feature: Feature) -> None:
        self._d[feature.underlying] = feature

    async def get(self, underlying: str) -> Feature | None:
        return self._d.get(underlying)


class InMemoryIVHistory:
    def __init__(self) -> None:
        self._d: dict[str, list[tuple[datetime, float]]] = {}

    async def append(self, underlying: str, iv: float, ts: datetime) -> None:
        self._d.setdefault(underlying, []).append((ts, iv))

    async def window(self, underlying: str, days: int = 365) -> list[float]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [iv for ts, iv in self._d.get(underlying, []) if ts >= cutoff]


class InMemoryCandidateRepository:
    def __init__(self) -> None:
        self._d: dict[str, list[Candidate]] = {}

    async def save(self, candidates: list[Candidate]) -> None:
        for c in candidates:
            self._d.setdefault(c.underlying, []).append(c)

    async def latest(self, underlying: str, limit: int = 20) -> list[Candidate]:
        rows = self._d.get(underlying, [])
        return sorted(rows, key=lambda c: c.score, reverse=True)[:limit]
