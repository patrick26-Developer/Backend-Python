"""Diffusion temps réel des événements (Module 12) — pour les flux SSE.

- `InMemoryEventPublisher` : *broadcast* aux abonnés du **même** process (dev,
  mono-instance).
- `RedisEventPublisher` : Redis **pub/sub** → tous les abonnés de **toutes** les
  instances reçoivent l'événement (fan-out multi-instance).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator

from taskman.domain.events import DomainEvent

_CHANNEL = "taskman:events"


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()

    async def publish(self, event: DomainEvent) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(event)

    async def subscribe(self) -> AsyncGenerator[DomainEvent, None]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    async def close(self) -> None:
        self._subscribers.clear()


class RedisEventPublisher:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]

    async def publish(self, event: DomainEvent) -> None:
        await self._redis.publish(_CHANNEL, event.model_dump_json())

    async def subscribe(self) -> AsyncGenerator[DomainEvent, None]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield DomainEvent(**json.loads(message["data"]))
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(_CHANNEL)
                await pubsub.aclose()

    async def close(self) -> None:
        await self._redis.aclose()


def build_event_publisher(redis_url: str | None) -> InMemoryEventPublisher | RedisEventPublisher:
    return RedisEventPublisher(redis_url) if redis_url else InMemoryEventPublisher()
