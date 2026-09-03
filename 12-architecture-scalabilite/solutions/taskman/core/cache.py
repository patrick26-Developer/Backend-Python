"""Abstraction de cache : un `Protocol` + deux implémentations.

- `InMemoryCache` : dict + TTL. Par instance → incohérent en multi-instance,
  mais parfait en dev et en test.
- `RedisCache` : partagé entre toutes les instances de l'API.

Choix à l'exécution selon `APP_REDIS_URL` (voir `build_cache`).
"""

from __future__ import annotations

import time
from typing import Protocol


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, *, ttl: int) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> None: ...

    async def close(self) -> None: ...


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}  # key -> (expires_at, value)

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, *, ttl: int) -> None:
        self._store[key] = (time.monotonic() + ttl, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._store if k.startswith(prefix)]:
            self._store.pop(key, None)

    async def close(self) -> None:
        self._store.clear()


class RedisCache:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]

    async def get(self, key: str) -> str | None:
        value: str | None = await self._redis.get(key)
        return value

    async def set(self, key: str, value: str, *, ttl: int) -> None:
        await self._redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        # SCAN (non bloquant) plutôt que KEYS (bloque Redis sur les grosses bases).
        async for key in self._redis.scan_iter(match=f"{prefix}*"):
            await self._redis.delete(key)

    async def close(self) -> None:
        await self._redis.aclose()


def build_cache(redis_url: str | None) -> Cache:
    return RedisCache(redis_url) if redis_url else InMemoryCache()
