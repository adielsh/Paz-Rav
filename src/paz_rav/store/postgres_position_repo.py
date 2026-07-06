"""Postgres-backed position ledger (asyncpg).

Unlike candidates (always a fresh insert per scan), a position is *mutated* over its
life — the Exit Manager sets/clears ``alert`` on every sweep, then the user's manual
close fills in the rest — so ``save`` is an upsert keyed on the position's UUID.
``connect()`` creates the pool and ensures the schema, so first run is turnkey.
"""

from __future__ import annotations

import json

from paz_rav.positions.base import Position
from paz_rav.store.serialize import position_from_dict, position_to_dict

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id          TEXT        PRIMARY KEY,
    underlying  TEXT        NOT NULL,
    status      TEXT        NOT NULL,
    opened_at   TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload     JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_positions_underlying_status
    ON positions (underlying, status);
"""


class PostgresPositionRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresPositionRepository":
        import asyncpg

        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def save(self, position: Position) -> None:
        payload = json.dumps(position_to_dict(position))
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO positions (id, underlying, status, opened_at, updated_at, payload)
                VALUES ($1, $2, $3, $4, now(), $5)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    updated_at = now(),
                    payload = EXCLUDED.payload
                """,
                position.id, position.underlying, position.status, position.opened_at, payload,
            )

    async def get(self, position_id: str) -> Position | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT payload FROM positions WHERE id = $1", position_id,
            )
        return position_from_dict(json.loads(row["payload"])) if row else None

    async def list_open(self, underlying: str | None = None) -> list[Position]:
        return await self._list(status="open", underlying=underlying)

    async def list_all(self, underlying: str | None = None) -> list[Position]:
        return await self._list(status=None, underlying=underlying)

    async def _list(self, *, status: str | None, underlying: str | None) -> list[Position]:
        clauses, params = [], []
        if status is not None:
            params.append(status)
            clauses.append(f"status = ${len(params)}")
        if underlying is not None:
            params.append(underlying)
            clauses.append(f"underlying = ${len(params)}")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT payload FROM positions {where} ORDER BY opened_at DESC", *params,
            )
        return [position_from_dict(json.loads(r["payload"])) for r in rows]

    async def close(self) -> None:
        await self.pool.close()
