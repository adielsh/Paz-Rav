"""Scheduler — a small in-process timer that scans all underlyings on a loop.

A component, not a service (docs/ARCHITECTURE.md): it just calls ``Pipeline.run_once`` for each
underlying every ``interval`` seconds. Scans run concurrently but the pipeline itself
never blocks the event loop (all I/O is async).
"""

from __future__ import annotations

import asyncio
import logging

from paz_rav.pipeline import Pipeline

log = logging.getLogger("paz_rav.scheduler")


class Scheduler:
    def __init__(self, pipeline: Pipeline, underlyings: list[str], interval: float = 60.0,
                 today=None):
        self.pipeline = pipeline
        self.underlyings = underlyings
        self.interval = interval
        self.today = today  # pin the "as-of" date for offline/fixture runs; None = real today
        self._stop = asyncio.Event()

    async def scan_all(self) -> None:
        """One scan cycle across every underlying, concurrently."""
        results = await asyncio.gather(
            *(self.pipeline.run_once(u, today=self.today) for u in self.underlyings),
            return_exceptions=True,
        )
        for u, r in zip(self.underlyings, results):
            if isinstance(r, Exception):
                log.warning("scan failed for %s: %s", u, r)

    async def run(self) -> None:
        """Loop until ``stop()``; sleeps ``interval`` between cycles."""
        while not self._stop.is_set():
            await self.scan_all()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()
