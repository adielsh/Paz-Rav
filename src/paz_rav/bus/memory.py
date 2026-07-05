"""In-memory bus — records publishes and fans out to live subscribers. For tests/dev."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class InMemoryBus:
    def __init__(self) -> None:
        self.published: dict[str, list[dict]] = {}
        self._subs: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, channel: str, payload: dict) -> None:
        self.published.setdefault(channel, []).append(payload)
        for q in self._subs.get(channel, []):
            q.put_nowait(payload)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(channel, []).append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs[channel].remove(q)
