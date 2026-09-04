from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from shorturl.api import create_app
from shorturl.config import Settings, get_settings
from shorturl.db import Base, create_engine, create_session_factory, get_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DB_URL, base_url="http://sho.rt", alias_length=5)


@pytest_asyncio.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


@pytest.fixture
def app(settings: Settings, session_factory: async_sessionmaker[AsyncSession]):  # type: ignore[no-untyped-def]
    application = create_app(settings)
    application.state.session_factory = session_factory

    async def _override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = _override
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest_asyncio.fixture
async def async_client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as c:
        yield c
