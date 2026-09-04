from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from shopfast import security
from shopfast.config import Settings, get_settings
from shopfast.db import Base, create_engine, create_session_factory, get_session
from shopfast.main import create_app
from shopfast.models import UserRow
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

PWD = "password-de-test-123"


@pytest.fixture(autouse=True)
def _fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """argon2 « vrai » est trop lent pour une suite : hachage trivial en test."""
    monkeypatch.setattr(security, "hash_password", lambda p: f"fake::{p}")
    monkeypatch.setattr(security, "verify_password", lambda p, h: h == f"fake::{p}")


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite://", env="test")


@pytest_asyncio.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


@pytest_asyncio.fixture
async def app(  # type: ignore[no-untyped-def]
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
):
    application = create_app(settings)
    application.state.session_factory = session_factory

    async def _override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = _override
    application.dependency_overrides[get_settings] = lambda: settings
    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api(app) -> AsyncIterator[httpx.AsyncClient]:  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register_and_login(
    api: httpx.AsyncClient, email: str, *, role: str, session_factory: async_sessionmaker
) -> str:  # type: ignore[type-arg]
    await api.post("/auth/register", json={"email": email, "password": PWD})
    if role == "admin":
        async with session_factory() as s:
            await s.execute(update(UserRow).where(UserRow.email == email).values(role="admin"))
            await s.commit()
    r = await api.post("/auth/login", json={"email": email, "password": PWD})
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def customer(api, session_factory):  # type: ignore[no-untyped-def]
    token = await _register_and_login(
        api, "cust@test.co", role="customer", session_factory=session_factory
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_customer(api, session_factory):  # type: ignore[no-untyped-def]
    token = await _register_and_login(
        api, "other@test.co", role="customer", session_factory=session_factory
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin(api, session_factory):  # type: ignore[no-untyped-def]
    token = await _register_and_login(
        api, "admin@test.co", role="admin", session_factory=session_factory
    )
    return {"Authorization": f"Bearer {token}"}
