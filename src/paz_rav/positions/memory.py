"""In-memory position ledger — for tests and offline dev."""

from __future__ import annotations

from paz_rav.positions.base import Position


class InMemoryPositionRepository:
    def __init__(self) -> None:
        self._d: dict[str, Position] = {}

    async def save(self, position: Position) -> None:
        self._d[position.id] = position

    async def get(self, position_id: str) -> Position | None:
        return self._d.get(position_id)

    async def list_open(self, underlying: str | None = None) -> list[Position]:
        return [p for p in self._d.values() if p.status == "open"
                and (underlying is None or p.underlying == underlying)]

    async def list_all(self, underlying: str | None = None) -> list[Position]:
        rows = list(self._d.values())
        return [p for p in rows if underlying is None or p.underlying == underlying]
