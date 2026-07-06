"""Postgres-backed AccessRequestRepository (asyncpg).

Keyed on email (one request per email, re-approved in place if it somehow gets asked
for twice) — a pending approval must survive a container restart, since the whole point
is the owner might click the emailed link hours or days after the request was made.
"""

from __future__ import annotations

from datetime import datetime, timezone

from paz_rav.access_requests import AccessRequest, new_token

SCHEMA = """
CREATE TABLE IF NOT EXISTS access_requests (
    email        TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'pending',
    token        TEXT NOT NULL UNIQUE,
    requested_at TIMESTAMPTZ NOT NULL,
    decided_at   TIMESTAMPTZ
);
"""


def _row_to_request(row) -> AccessRequest:
    return AccessRequest(email=row["email"], status=row["status"], token=row["token"],
                         requested_at=row["requested_at"], decided_at=row["decided_at"])


class PostgresAccessRequestRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresAccessRequestRepository":
        import asyncpg

        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def get(self, email: str) -> AccessRequest | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM access_requests WHERE email = $1", email)
        return _row_to_request(row) if row else None

    async def create_pending(self, email: str) -> AccessRequest:
        now = datetime.now(timezone.utc)
        token = new_token()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO access_requests (email, status, token, requested_at)
                VALUES ($1, 'pending', $2, $3)
                ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
                RETURNING *
                """,
                email, token, now,
            )
        return _row_to_request(row)

    async def approve_by_token(self, token: str) -> AccessRequest | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE access_requests SET status = 'approved', decided_at = now()
                WHERE token = $1
                RETURNING *
                """,
                token,
            )
        return _row_to_request(row) if row else None

    async def close(self) -> None:
        await self.pool.close()
