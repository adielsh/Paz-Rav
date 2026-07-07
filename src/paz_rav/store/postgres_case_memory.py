"""Postgres + pgvector case memory — indexed similarity search over closed cases.

Same shape as InMemoryCaseMemory, backed by the `vector` type so retrieval is an indexed
cosine search instead of a full scan. Requires the pgvector extension (the
`pgvector/pgvector:pg16` image in docker-compose provides it); ``connect()`` creates the
extension + table + index, so first run is turnkey.

If the extension can't be created (e.g. a plain Postgres image), ``connect()`` raises and
the caller falls back to InMemoryCaseMemory — the debate still runs, just without indexed
recall.
"""

from __future__ import annotations

from paz_rav.store.case_memory import VECTOR_DIM, Case, Neighbor

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS case_memory (
    position_id  TEXT PRIMARY KEY,
    underlying   TEXT NOT NULL,
    strategy     TEXT NOT NULL,
    realized_pnl DOUBLE PRECISION NOT NULL,
    close_reason TEXT,
    won          BOOLEAN NOT NULL,
    summary      TEXT NOT NULL,
    embedding    vector({VECTOR_DIM}) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_case_memory_embedding
    ON case_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
CREATE INDEX IF NOT EXISTS ix_case_memory_strategy ON case_memory (strategy);
"""


def _to_literal(vector: tuple[float, ...]) -> str:
    """pgvector text input format: '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class PostgresCaseMemory:
    def __init__(self, pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresCaseMemory":
        import asyncpg

        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def add(self, case: Case) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO case_memory
                    (position_id, underlying, strategy, realized_pnl, close_reason,
                     won, summary, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (position_id) DO UPDATE SET
                    realized_pnl = EXCLUDED.realized_pnl,
                    close_reason = EXCLUDED.close_reason,
                    won = EXCLUDED.won,
                    summary = EXCLUDED.summary,
                    embedding = EXCLUDED.embedding
                """,
                case.position_id, case.underlying, case.strategy, case.realized_pnl,
                case.close_reason, case.won, case.summary, _to_literal(case.vector),
            )

    async def similar(self, vector: tuple[float, ...], *, strategy: str | None = None,
                      k: int = 5) -> list[Neighbor]:
        params: list = [_to_literal(vector)]
        where = ""
        if strategy is not None:
            params.append(strategy)
            where = "WHERE strategy = $2"
        # 1 - cosine_distance = cosine similarity; order by distance ascending (nearest first)
        rows = await self._fetch(
            f"""
            SELECT position_id, underlying, strategy, realized_pnl, close_reason, won,
                   summary, embedding, 1 - (embedding <=> $1) AS similarity
            FROM case_memory {where}
            ORDER BY embedding <=> $1
            LIMIT {int(k)}
            """,
            params,
        )
        out: list[Neighbor] = []
        for r in rows:
            emb = tuple(float(x) for x in str(r["embedding"]).strip("[]").split(",") if x)
            out.append(Neighbor(
                Case(position_id=r["position_id"], underlying=r["underlying"],
                     strategy=r["strategy"], vector=emb, realized_pnl=r["realized_pnl"],
                     close_reason=r["close_reason"], won=r["won"], summary=r["summary"]),
                similarity=float(r["similarity"]),
            ))
        return out

    async def count(self) -> int:
        async with self.pool.acquire() as conn:
            return int(await conn.fetchval("SELECT count(*) FROM case_memory"))

    async def _fetch(self, sql: str, params: list):
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, *params)

    async def close(self) -> None:
        await self.pool.close()
