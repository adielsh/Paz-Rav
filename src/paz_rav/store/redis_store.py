"""Redis-backed hot stores — current features + the IV-history time series.

Create the client with ``decode_responses=True``. Works with a real Redis (via
docker-compose) or fakeredis in tests — the code is identical.
"""

from __future__ import annotations

from datetime import datetime, timezone

from paz_rav.contracts import Feature
from paz_rav.store.serialize import feature_from_json, feature_to_json

_FEATURE_KEY = "feat:{}"
_IVHIST_KEY = "ivhist:{}"


class RedisFeatureStore:
    def __init__(self, client) -> None:
        self.r = client

    async def put(self, feature: Feature) -> None:
        await self.r.set(_FEATURE_KEY.format(feature.underlying), feature_to_json(feature))

    async def get(self, underlying: str) -> Feature | None:
        raw = await self.r.get(_FEATURE_KEY.format(underlying))
        return feature_from_json(raw) if raw else None


class RedisIVHistory:
    """ATM IV time series in a sorted set scored by epoch seconds."""

    def __init__(self, client) -> None:
        self.r = client

    async def append(self, underlying: str, iv: float, ts: datetime) -> None:
        score = ts.timestamp()
        member = f"{score}:{iv}"  # score keeps members unique; iv is parsed back out
        await self.r.zadd(_IVHIST_KEY.format(underlying), {member: score})

    async def window(self, underlying: str, days: int = 365) -> list[float]:
        lo = datetime.now(timezone.utc).timestamp() - days * 86400
        members = await self.r.zrangebyscore(_IVHIST_KEY.format(underlying), lo, "+inf")
        out: list[float] = []
        for m in members:
            m = m.decode() if isinstance(m, bytes) else m
            out.append(float(m.split(":", 1)[1]))
        return out
