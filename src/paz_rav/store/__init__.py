"""Storage — repositories behind interfaces (Repository pattern).

Protocols in ``base``; concrete backends alongside. In-memory for tests/offline, Redis
for hot state + IV history, Postgres for durable candidates and positions. Callers
depend on the Protocols, so swapping a backend never touches business logic.
"""

from paz_rav.store.base import CandidateRepository, FeatureStore, IVHistoryStore
from paz_rav.store.memory import (
    InMemoryCandidateRepository,
    InMemoryFeatureStore,
    InMemoryIVHistory,
)
from paz_rav.store.postgres_position_repo import PostgresPositionRepository
from paz_rav.store.postgres_store import PostgresCandidateRepository
from paz_rav.store.redis_store import RedisFeatureStore, RedisIVHistory

__all__ = [
    # interfaces
    "FeatureStore",
    "IVHistoryStore",
    "CandidateRepository",
    # in-memory
    "InMemoryFeatureStore",
    "InMemoryIVHistory",
    "InMemoryCandidateRepository",
    # redis
    "RedisFeatureStore",
    "RedisIVHistory",
    # postgres
    "PostgresCandidateRepository",
    "PostgresPositionRepository",
]
