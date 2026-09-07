"""Postgres-backed durable candidate repository (asyncpg).

The candidate is stored as JSONB with a few promoted columns for querying/ordering.
``connect()`` creates the pool and ensures the schema, so first run is turnkey.

This table is **append-only and high-volume**: every scan of every underlying inserts a
row per candidate, so a 60-second scheduler over nine names writes on the order of 60k
rows/day. Nothing but :meth:`latest` ever reads them, and only the newest few per
underlying at that. :meth:`_maybe_prune` is therefore not an optimisation — without it
the table grows without bound in the same database that holds real trading data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
import json

from paz_rav.store.serialize import candidate_from_dict, candidate_to_dict
from paz_rav.strategies.base import Candidate

log = logging.getLogger("paz_rav.store.candidates")

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
-- The read index above leads on `underlying`, so a prune filtering on `created_at`
-- alone cannot use it and would sequentially scan the whole table every hour.
CREATE INDEX IF NOT EXISTS ix_candidates_created
    ON candidates (created_at);
"""

#: How often the prune is allowed to run. Pruning on every ``save`` would issue a DELETE
#: roughly 40 times a minute to remove, almost always, nothing at all.
_PRUNE_EVERY = timedelta(hours=1)


class PostgresCandidateRepository:
    def __init__(self, pool, retention_days: int = 7) -> None:
        self.pool = pool
        self.retention_days = retention_days
        self._last_prune: datetime | None = None

    @classmethod
    async def connect(cls, dsn: str, retention_days: int = 7) -> "PostgresCandidateRepository":
        import asyncpg

        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool, retention_days=retention_days)

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
        await self._maybe_prune(now)

    async def _maybe_prune(self, now: datetime) -> None:
        """Drop candidates past the retention window, at most once per hour.

        Deliberately never raises: this runs on the scan path, and losing a scan because
        a housekeeping DELETE failed would be a worse outcome than the table staying
        large for another hour. It logs loudly instead of failing silently, so a prune
        that is genuinely broken is visible rather than merely absent.
        """
        if self.retention_days <= 0:
            return
        if self._last_prune is not None and now - self._last_prune < _PRUNE_EVERY:
            return
        # Set this before the DELETE, not after: if the delete fails we still want to
        # wait a full hour rather than retry on every save.
        self._last_prune = now
        cutoff = now - timedelta(days=self.retention_days)
        try:
            async with self.pool.acquire() as conn:
                status = await conn.execute(
                    "DELETE FROM candidates WHERE created_at < $1", cutoff)
        except Exception as e:
            log.warning("candidate prune failed (table will keep growing): %s", e)
            return
        # asyncpg returns the command tag, e.g. "DELETE 1234".
        deleted = status.rsplit(" ", 1)[-1] if isinstance(status, str) else "?"
        if deleted not in ("0", "?"):
            log.info("pruned %s candidates older than %s days", deleted, self.retention_days)

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
