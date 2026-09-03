"""Tests de durcissement (Module 10) : en-têtes, CORS, rate limit, taille de payload."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from taskman.api.deps import get_session
from taskman.api.ratelimit import InMemoryRateLimiter
from taskman.core.cache import InMemoryCache
from taskman.core.config import Settings
from taskman.main import create_app

PWD = "password-de-test-12345"


# --- en-têtes de sécurité --------------------------------------
async def test_security_headers_present(client: AsyncClient) -> None:
    h = (await client.get("/health")).headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in h


async def test_no_csp_on_docs(client: AsyncClient) -> None:
    # Swagger UI charge du JS depuis un CDN -> pas de CSP stricte sur /docs
    assert "content-security-policy" not in (await client.get("/openapi.json")).headers


async def test_no_hsts_outside_production(client: AsyncClient) -> None:
    assert "strict-transport-security" not in (await client.get("/health")).headers


# --- CORS ----------------------------------------------------
@pytest_asyncio.fixture
async def cors_client(
    session_factory: async_sessionmaker,
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        Settings(
            env="test",
            database_url="sqlite+aiosqlite://",
            log_json=False,
            cors_origins=["https://app.exemple.org"],
            rate_limit_enabled=False,
        )
    )
    app.state.cache = InMemoryCache()
    app.state.rate_limiter = InMemoryRateLimiter()

    async def _override() -> AsyncIterator:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_cors_allows_configured_origin(cors_client: AsyncClient) -> None:
    resp = await cors_client.get("/health", headers={"Origin": "https://app.exemple.org"})
    assert resp.headers["access-control-allow-origin"] == "https://app.exemple.org"


async def test_cors_rejects_unknown_origin(cors_client: AsyncClient) -> None:
    resp = await cors_client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in resp.headers


# --- rate limiting -----------------------------------------
@pytest_asyncio.fixture
async def limited_client(
    session_factory: async_sessionmaker,
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        Settings(
            env="test",
            database_url="sqlite+aiosqlite://",
            log_json=False,
            rate_limit_enabled=True,
            auth_rate_limit_per_minute=3,
        )
    )
    app.state.cache = InMemoryCache()
    app.state.rate_limiter = InMemoryRateLimiter()

    async def _override() -> AsyncIterator:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_auth_rate_limit_returns_429(limited_client: AsyncClient) -> None:
    codes = []
    for i in range(5):
        r = await limited_client.post(
            "/auth/login", data={"username": f"x{i}@y.co", "password": PWD}
        )
        codes.append(r.status_code)
    # 3 tentatives autorisées (401), puis 429
    assert codes.count(429) >= 1
    last = await limited_client.post("/auth/login", data={"username": "z@y.co", "password": PWD})
    assert last.status_code == 429
    assert last.json()["code"] == "rate_limited"
    assert int(last.headers["retry-after"]) > 0


async def test_rate_limit_is_per_ip(limited_client: AsyncClient) -> None:
    for _ in range(4):
        await limited_client.post("/auth/login", data={"username": "a@y.co", "password": PWD})
    # une autre IP (X-Forwarded-For) n'est pas affectée
    r = await limited_client.post(
        "/auth/login",
        data={"username": "b@y.co", "password": PWD},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 401  # pas 429


# --- taille du payload -------------------------------------
async def test_oversized_payload_is_413(client: AsyncClient) -> None:
    huge = "x" * 2_000_000  # > 1 Mio
    resp = await client.post("/auth/register", json={"email": "a@b.co", "password": huge})
    assert resp.status_code == 413
    assert resp.json()["code"] == "payload_too_large"


# --- BOLA (rappel Module 06, garde-fou OWASP #1) ---------
async def test_metrics_still_internal_only(client: AsyncClient) -> None:
    # /metrics répond mais ne doit jamais être dans le schéma public
    assert (await client.get("/metrics")).status_code == 200
    assert "/metrics" not in (await client.get("/openapi.json")).json()["paths"]
