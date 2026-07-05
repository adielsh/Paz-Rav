"""Storage interfaces — the Repository pattern.

Business logic depends on these Protocols, never on Redis or Postgres directly. That
is what lets the concrete backend change without touching callers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate


class FeatureStore(Protocol):
    """Hot, current per-underlying features (backed by Redis)."""

    async def put(self, feature: Feature) -> None: ...

    async def get(self, underlying: str) -> Feature | None: ...


class IVHistoryStore(Protocol):
    """Time series of ATM IV per underlying — this is what makes IV rank real."""

    async def append(self, underlying: str, iv: float, ts: datetime) -> None: ...

    async def window(self, underlying: str, days: int = 365) -> list[float]: ...


class CandidateRepository(Protocol):
    """Durable ranked candidates (backed by Postgres)."""

    async def save(self, candidates: list[Candidate]) -> None: ...

    async def latest(self, underlying: str, limit: int = 20) -> list[Candidate]: ...
