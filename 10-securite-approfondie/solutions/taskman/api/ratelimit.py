"""Limitation de débit (*rate limiting*) — fenêtre fixe.

`InMemoryRateLimiter` : compteur par instance (dev / mono-instance).
`RedisRateLimiter` : compteur partagé (multi-instance) via `INCR` + `EXPIRE`.
"""

from __future__ import annotations

import time
from typing import Protocol

from fastapi import Request

from taskman.core.exceptions import TooManyRequestsError


class RateLimiter(Protocol):
    async def hit(self, key: str, *, limit: int, window: int) -> int:
        """Incrémente le compteur de `key`. Renvoie le nombre de secondes à
        attendre si la limite est franchie, `0` sinon."""
        ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = {}  # key -> (reset_at, count)

    async def hit(self, key: str, *, limit: int, window: int) -> int:
        now = time.monotonic()
        reset_at, count = self._buckets.get(key, (now + window, 0))
        if now >= reset_at:
            reset_at, count = now + window, 0
        count += 1
        self._buckets[key] = (reset_at, count)
        return int(reset_at - now) + 1 if count > limit else 0


class RedisRateLimiter:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]

    async def hit(self, key: str, *, limit: int, window: int) -> int:
        count = int(await self._redis.incr(key))
        if count == 1:
            await self._redis.expire(key, window)
        if count > limit:
            return int(await self._redis.ttl(key)) or window
        return 0


def build_rate_limiter(redis_url: str | None) -> RateLimiter:
    return RedisRateLimiter(redis_url) if redis_url else InMemoryRateLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:  # posé par le reverse proxy en prod (Module 11)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def auth_rate_limit(request: Request) -> None:
    """Dépendance de route : limite les endpoints d'authentification par IP
    (anti-*brute force*). Config : `APP_AUTH_RATE_LIMIT_PER_MINUTE`."""
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    limiter: RateLimiter = request.app.state.rate_limiter
    route = request.scope.get("route")
    scope = getattr(route, "path", request.url.path)
    key = f"ratelimit:{scope}:{_client_ip(request)}"
    retry_after = await limiter.hit(key, limit=settings.auth_rate_limit_per_minute, window=60)
    if retry_after:
        raise TooManyRequestsError(retry_after)
