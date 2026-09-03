"""Tests unitaires de `InMemoryCache` et `build_cache`."""

from __future__ import annotations

import time

import pytest

from taskman.core.cache import InMemoryCache, RedisCache, build_cache


async def test_set_get_delete() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v", ttl=60)
    assert await cache.get("k") == "v"
    await cache.delete("k")
    assert await cache.get("k") is None


async def test_missing_key_returns_none() -> None:
    assert await InMemoryCache().get("absent") is None


async def test_ttl_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = InMemoryCache()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    await cache.set("k", "v", ttl=10)
    now[0] = 1009.0
    assert await cache.get("k") == "v"
    now[0] = 1011.0
    assert await cache.get("k") is None


async def test_delete_prefix() -> None:
    cache = InMemoryCache()
    await cache.set("project:7:stats", "a", ttl=60)
    await cache.set("project:7:members", "b", ttl=60)
    await cache.set("project:8:stats", "c", ttl=60)
    await cache.delete_prefix("project:7:")
    assert await cache.get("project:7:stats") is None
    assert await cache.get("project:7:members") is None
    assert await cache.get("project:8:stats") == "c"


def test_build_cache_selects_implementation() -> None:
    assert isinstance(build_cache(None), InMemoryCache)
    # une URL -> RedisCache (sans connexion réelle tant qu'on ne l'utilise pas)
    assert isinstance(build_cache("redis://localhost:6379/0"), RedisCache)
