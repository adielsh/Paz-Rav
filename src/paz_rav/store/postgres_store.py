"""Postgres-backed durable candidate repository (asyncpg).

The candidate is stored as JSONB with a few promoted columns for querying/ordering.
``connect()`` creates the pool and ensures the schema, so first run is turnkey.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from paz_rav.store.serialize import candidate_from_dict, candidate_to_dict
from paz_rav.strategies.base import Candidate

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id          BIGSERIAL PRIMARY KEY,
    underlying  TEXT        NOT NULL,
    strategy    TEXT        NOT NULL,
    score       DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload     JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_candidates_underlying_created
    ON candidates (underlying, created_at DESC);
"""


class PostgresCandidateRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresCandidateRepository":
        import asyncpg

        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def save(self, candidates: list[Candidate]) -> None:
        if not candidates:
            return
        now = datetime.now(timezone.utc)
        rows = [
            (c.underlying, c.strategy, c.score, now, json.dumps(candidate_to_dict(c)))
            for c in candidates
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO candidates (underlying, strategy, score, created_at, payload) "
                "VALUES ($1, $2, $3, $4, $5)",
                rows,
            )

    async def latest(self, underlying: str, limit: int = 20) -> list[Candidate]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload FROM candidates WHERE underlying = $1 "
                "ORDER BY created_at DESC, score DESC LIMIT $2",
                underlying, limit,
            )
        return [candidate_from_dict(json.loads(r["payload"])) for r in rows]

    async def close(self) -> None:
        await self.pool.close()
