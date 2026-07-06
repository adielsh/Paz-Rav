"""In-memory bus — records publishes and delivers to live subscribers."""

import asyncio

from paz_rav.bus import CH_FEATURES, InMemoryBus


def test_bus_records_and_delivers():
    async def go():
        bus = InMemoryBus()
        received: list[dict] = []

        async def subscriber():
            async for msg in bus.subscribe(CH_FEATURES):
                received.append(msg)
                break

        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.01)              # let the subscriber register
        await bus.publish(CH_FEATURES, {"underlying": "SPY", "iv_rank": 42})
        await asyncio.wait_for(task, timeout=1.0)
        return received, bus.published

    received, published = asyncio.run(go())
    assert received == [{"underlying": "SPY", "iv_rank": 42}]
    assert published[CH_FEATURES] == [{"underlying": "SPY", "iv_rank": 42}]
