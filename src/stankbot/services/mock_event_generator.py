"""Mock event generator — background task that emits random events."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random

from stankbot.services.mock_event_bridge import MockEventBridge

log = logging.getLogger(__name__)

_DEFAULT_USERS = [
    (1001, "Alice"),
    (1002, "Bob"),
    (1003, "Charlie"),
    (1004, "Diana"),
    (1005, "Eve"),
]


class MockEventGenerator:
    """Spawns an asyncio task that calls the bridge at random intervals."""

    def __init__(self, bridge: MockEventBridge, guild_id: int, interval: int = 5) -> None:
        self.bridge = bridge
        self.guild_id = guild_id
        self.interval = interval
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        log.info("Mock event generator started (guild=%d, interval=%ds)", self.guild_id, self.interval)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        log.info("Mock event generator stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.interval)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Mock event generator tick failed")

    async def _tick(self) -> None:
        roll = random.random()
        user_id, name = random.choice(_DEFAULT_USERS)

        if roll < 0.70:
            await self.bridge.inject_stank(self.guild_id, user_id, name)
        elif roll < 0.85:
            await self.bridge.inject_break(self.guild_id, user_id, name)
        elif roll < 0.95:
            # Reaction on a recent message — just use a fixed message id for now.
            await self.bridge.inject_reaction(self.guild_id, 10_000_001, user_id)
        else:
            await self.bridge.inject_noise(self.guild_id, user_id, name)
