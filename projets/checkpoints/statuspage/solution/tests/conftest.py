from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from statuspage.api import create_app, get_session
from statuspage.config import Settings, get_settings
from statuspage.db import Base, create_engine, create_session_factory
from statuspage.monitor import Monitor
from statuspage.observability import Metrics

TEST_DB_URL = "sqlite+aiosqlite://"


def _ok_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200)))


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DB_URL,
        log_json=False,
        worker_enabled=False,
        outage_consecutive_failures=3,
        ready_max_worker_staleness_seconds=30.0,
    )


@pytest_asyncio.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


@pytest.fixture
def metrics() -> Metrics:
    return Metrics()


@pytest_asyncio.fixture
async def app(  # type: ignore[no-untyped-def]
    settings: Settings, session_factory: async_sessionmaker[AsyncSession], metrics: Metrics
):
    application = create_app(settings)
    # les tests câblent l'état à la main (pas de lifespan sous ASGITransport) :
    application.state.session_factory = session_factory
    application.state.metrics = metrics
    application.state.monitor = Monitor(session_factory, settings, metrics, _ok_client())

    async def _override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = _override
    application.dependency_overrides[get_settings] = lambda: settings
    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
