"""Redis pub/sub bus — live push to the api module, which fans out over WebSocket."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator


class RedisBus:
    def __init__(self, client) -> None:
        self.r = client

    async def publish(self, channel: str, payload: dict) -> None:
        await self.r.publish(channel, json.dumps(payload))

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        pubsub = self.r.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                data = msg["data"]
                yield json.loads(data.decode() if isinstance(data, bytes) else data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
