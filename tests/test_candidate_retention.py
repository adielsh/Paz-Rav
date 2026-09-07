"""Retention on the Postgres candidate table.

The `candidates` table is append-only and high-volume — a 60-second scan over nine
underlyings writes on the order of 60k rows/day, into the same database that holds real
trading data. The prune is the only thing bounding it, so its logic is worth testing even
though the repository itself talks to a Postgres that CI does not have.

A fake pool stands in for asyncpg: it records every statement, which is enough to assert
*when* a DELETE is issued and *what cutoff* it carries. Async methods are driven with
asyncio.run, matching tests/test_store.py — no pytest-asyncio plugin needed.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from paz_rav.store.postgres_store import PostgresCandidateRepository
from paz_rav.strategies import make_strategy


def _run(coro):
    return asyncio.run(coro)


class FakeConn:
    def __init__(self, log, fail_on_delete=False):
        self.log = log
        self.fail_on_delete = fail_on_delete

    async def executemany(self, sql, rows):
        self.log.append(("executemany", sql, rows))

    async def execute(self, sql, *args):
        if self.fail_on_delete and sql.startswith("DELETE"):
            raise RuntimeError("connection reset")
        self.log.append(("execute", sql, args))
        return "DELETE 1234"


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self, fail_on_delete=False):
        self.log = []
        self.conn = FakeConn(self.log, fail_on_delete=fail_on_delete)

    def acquire(self):
        return FakeAcquire(self.conn)

    def deletes(self):
        return [e for e in self.log if e[0] == "execute" and e[1].startswith("DELETE")]


def _candidate():
    return make_strategy("iron_condor").build(
        underlying="SPY", spot=100.0, dte=45,
        put_long=90.0, put_short=95.0, call_short=105.0, call_long=110.0,
        credit=1.0, sigma=0.20,
    )


def test_first_save_prunes_and_inserts():
    pool = FakePool()
    repo = PostgresCandidateRepository(pool, retention_days=7)
    _run(repo.save([_candidate()]))

    assert any(e[0] == "executemany" for e in pool.log), "the insert must still happen"
    assert len(pool.deletes()) == 1


def test_prune_is_throttled_to_once_an_hour():
    """The scan path calls save ~40x/minute; pruning on each would be pure waste."""
    pool = FakePool()
    repo = PostgresCandidateRepository(pool, retention_days=7)
    for _ in range(5):
        _run(repo.save([_candidate()]))
    assert len(pool.deletes()) == 1

    # Wind the clock back past the throttle and it prunes again.
    repo._last_prune = datetime.now(timezone.utc) - timedelta(hours=2)
    _run(repo.save([_candidate()]))
    assert len(pool.deletes()) == 2


def test_cutoff_is_retention_days_back():
    pool = FakePool()
    repo = PostgresCandidateRepository(pool, retention_days=3)
    before = datetime.now(timezone.utc)
    _run(repo.save([_candidate()]))

    (_, _, args), = pool.deletes()
    cutoff = args[0]
    expected = before - timedelta(days=3)
    assert abs((cutoff - expected).total_seconds()) < 5


def test_zero_retention_disables_pruning():
    """A deliberate opt-out must never delete anything."""
    pool = FakePool()
    repo = PostgresCandidateRepository(pool, retention_days=0)
    _run(repo.save([_candidate()]))
    assert pool.deletes() == []


def test_prune_failure_does_not_break_the_scan():
    """Housekeeping must not be able to take down the pipeline that feeds the UI."""
    pool = FakePool(fail_on_delete=True)
    repo = PostgresCandidateRepository(pool, retention_days=7)
    _run(repo.save([_candidate()]))          # must not raise
    assert any(e[0] == "executemany" for e in pool.log), "the insert still lands"


def test_empty_save_touches_nothing():
    pool = FakePool()
    repo = PostgresCandidateRepository(pool, retention_days=7)
    _run(repo.save([]))
    assert pool.log == []
