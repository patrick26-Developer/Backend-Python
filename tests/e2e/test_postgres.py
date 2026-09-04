"""Tests d'intégration sur un **vrai PostgreSQL** (via testcontainers + Docker).

SQLite est parfait pour un feedback rapide, mais il diffère de PostgreSQL (types,
`ILIKE`, contraintes, transactions). Ces tests attrapent ce que SQLite laisse passer.

    pytest -m e2e            # nécessite Docker
    pytest -m "not e2e"      # les ignore (défaut en local rapide)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from taskman.api.deps import get_session
from taskman.core.config import Settings
from taskman.db.base import Base
from taskman.db.engine import create_engine, create_session_factory
from taskman.main import create_app

pytestmark = pytest.mark.e2e

PWD = "password-de-test-12345"


PG_IMAGE = os.getenv("TEST_PG_IMAGE", "postgres:17-alpine")


@pytest.fixture(scope="module")
def postgres_url() -> str:
    tc = pytest.importorskip("testcontainers.postgres")
    try:
        container = tc.PostgresContainer(PG_IMAGE, driver="asyncpg")
        container.start()
    except Exception as exc:  # Docker absent / non démarré
        pytest.skip(f"Docker indisponible pour les tests e2e : {exc}")
    url = container.get_connection_url()
    yield url
    container.stop()


@pytest_asyncio.fixture
async def pg_engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_client(pg_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    factory: async_sessionmaker = create_session_factory(pg_engine)
    app = create_app(
        Settings(
            env="test",
            database_url="postgresql+asyncpg://x",
            log_json=False,
            rate_limit_enabled=False,
        )
    )
    from taskman.api.ratelimit import InMemoryRateLimiter
    from taskman.core.cache import InMemoryCache
    from taskman.realtime import InMemoryEventPublisher

    # ASGITransport ne joue pas le `lifespan` : on pose à la main l'état que les
    # dépendances attendent dans `app.state` (comme le fait `tests/conftest.py`).
    app.state.cache = InMemoryCache()
    app.state.event_publisher = InMemoryEventPublisher()
    app.state.rate_limiter = InMemoryRateLimiter()

    async def _override() -> AsyncIterator:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/v1/auth/register", json={"email": "e2e@x.co", "password": PWD})
        r = await c.post("/v1/auth/login", data={"username": "e2e@x.co", "password": PWD})
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield c
    app.dependency_overrides.clear()


async def test_full_flow_on_real_postgres(pg_client: AsyncClient) -> None:
    pid = (await pg_client.post("/v1/projects", json={"name": "Réel"})).json()["id"]

    # ILIKE (insensible à la casse) — comportement PostgreSQL, pas SQLite
    await pg_client.post(
        "/v1/tasks", json={"title": "Documenter l'ARCHItecture", "project_id": pid}
    )
    page = (await pg_client.get("/v1/tasks", params={"q": "archi"})).json()
    assert page["total"] == 1

    tid = page["items"][0]["id"]
    done = await pg_client.post(f"/v1/tasks/{tid}/complete")
    assert done.json()["status"] == "done" and done.json()["completed_at"]

    # la contrainte de clé étrangère est bien appliquée
    bad = await pg_client.post("/v1/tasks", json={"title": "x", "project_id": 999999})
    assert bad.status_code == 404


async def test_transaction_rollback_on_error(pg_client: AsyncClient) -> None:
    # un payload invalide ne doit RIEN laisser en base
    before = (await pg_client.get("/v1/tasks")).json()["total"]
    await pg_client.post("/v1/tasks", json={"title": "", "project_id": 1})  # 422
    after = (await pg_client.get("/v1/tasks")).json()["total"]
    assert before == after
