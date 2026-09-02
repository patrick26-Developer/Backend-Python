"""Fixtures partagées (Module 04 : base de données de test).

Chaque test tourne sur une base **SQLite en mémoire, neuve et isolée** :
- `db_engine` : un moteur async in-memory (StaticPool = 1 connexion partagée, donc
  la base persiste le temps du test), tables créées via `Base.metadata.create_all` ;
- `db_session` : une session, pour tester les repositories directement ;
- `client` : un `httpx.AsyncClient` sur l'app, avec `get_session` **surchargé** pour
  utiliser le moteur de test.

`httpx.AsyncClient` + `ASGITransport` : on teste l'app sans serveur réseau, dans
le même *event loop* (indispensable pour l'async SQLite). Détaillé au Module 07.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from taskman.core.config import Settings
from taskman.db.base import Base
from taskman.db.engine import create_engine, create_session_factory
from taskman.db.session import get_session
from taskman.main import create_app

TEST_DB_URL = "sqlite+aiosqlite://"  # en mémoire


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine(TEST_DB_URL)  # StaticPool + PRAGMA foreign_keys=ON
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(db_engine)


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        Settings(env="test", database_url=TEST_DB_URL, log_json=False, log_level="WARNING")
    )

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
