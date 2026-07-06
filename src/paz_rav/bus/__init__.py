"""Message bus — live push to the dashboard (Observer pattern).

Publishers announce "something changed" on a channel; the api module fans it out to
the browser over WebSocket. Publishers never know who is listening. In-memory backend
for tests/dev, Redis pub/sub for runtime.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from paz_rav.bus.memory import InMemoryBus
from paz_rav.bus.redis_bus import RedisBus

# Channel names the whole system agrees on.
CH_FEATURES = "ui.features"
CH_CANDIDATES = "ui.candidates"
CH_RECS = "ui.recs"


class Bus(Protocol):
    async def publish(self, channel: str, payload: dict) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict]: ...


__all__ = ["Bus", "InMemoryBus", "RedisBus", "CH_FEATURES", "CH_CANDIDATES", "CH_RECS"]
