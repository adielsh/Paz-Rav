"""Reflection ledger — durable store of the strategic reflection agent's look-backs.

A reflection is a first-class **domain object** the product reads and reuses: the dashboard
lists them, and each new run is handed the recent ones for continuity ("last month I flagged
X — does the new data confirm it?"). That's app state, so it lives in Postgres, queried by
recency — the same Repository pattern as every other store here.

(This is distinct from Langfuse tracing of the reflection *run*: Postgres is the filing
cabinet — the document you retrieve and act on; Langfuse is the security camera — an
observability copy of the LLM call. See agents/reflection.py's `_maybe_trace`.)
"""

from __future__ import annotations

import json
from typing import Protocol

from paz_rav.agents.reflection import Reflection, reflection_from_dict, reflection_to_dict


class ReflectionRepository(Protocol):
    async def save(self, reflection: Reflection) -> None: ...

    async def recent(self, limit: int = 5) -> list[Reflection]: ...


class InMemoryReflectionRepository:
    """Default implementation (and the one tests use) — newest first."""

    def __init__(self) -> None:
        self._items: list[Reflection] = []

    async def save(self, reflection: Reflection) -> None:
        self._items.append(reflection)

    async def recent(self, limit: int = 5) -> list[Reflection]:
        return sorted(self._items, key=lambda r: r.created_at, reverse=True)[:limit]


SCHEMA = """
CREATE TABLE IF NOT EXISTS reflections (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL,
    sample_size INTEGER     NOT NULL,
    engine      TEXT        NOT NULL,
    payload     JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reflections_created_at ON reflections (created_at DESC);
"""


class PostgresReflectionRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresReflectionRepository":
        import asyncpg

        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def save(self, reflection: Reflection) -> None:
        payload = json.dumps(reflection_to_dict(reflection))
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reflections (created_at, sample_size, engine, payload)
                VALUES ($1, $2, $3, $4)
                """,
                reflection.created_at, reflection.sample_size, reflection.engine, payload,
            )

    async def recent(self, limit: int = 5) -> list[Reflection]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload FROM reflections ORDER BY created_at DESC LIMIT $1", limit,
            )
        return [reflection_from_dict(json.loads(r["payload"])) for r in rows]

    async def close(self) -> None:
        await self.pool.close()
