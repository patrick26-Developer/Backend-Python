"""Fixtures partagées (Module 06 : authentification).

- `db_engine` / `session_factory` / `db_session` : base SQLite in-memory jetable.
- `app` : l'app de test, avec `get_session` surchargé.
- `client` : client HTTP **non authentifié** (pour tester 401, /auth/*).
- `member_client` : client authentifié avec un compte `member`.
- `admin_client` : client authentifié avec un compte `admin` (rôle forcé en base).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from taskman.api.deps import get_session
from taskman.core.config import Settings
from taskman.db.base import Base
from taskman.db.engine import create_engine, create_session_factory
from taskman.db.models import UserRow
from taskman.main import create_app
from taskman.schemas import UserRole

TEST_DB_URL = "sqlite+aiosqlite://"
PWD = "password-de-test-12345"


@pytest.fixture(autouse=True)
def _fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """argon2 « vrai » coûte ~150 ms/hash — trop lent pour la suite. En test, on
    échange le hachage pour une fonction triviale (le comportement testé — égalité,
    rejet — est identique). Les tests de `core.security` gardent le vrai argon2."""
    from taskman.core import security

    def _fake_hash(plain: str) -> str:
        return f"fakehash::{plain}"

    def _fake_verify(plain: str, hashed: str) -> bool:
        return hashed == f"fakehash::{plain}"

    monkeypatch.setattr(security, "hash_password", _fake_hash)
    monkeypatch.setattr(security, "verify_password", _fake_verify)


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine(TEST_DB_URL)
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
async def app(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[FastAPI]:
    application = create_app(
        Settings(env="test", database_url=TEST_DB_URL, log_json=False, log_level="WARNING")
    )

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = _override_get_session
    yield application
    application.dependency_overrides.clear()


def _new_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with _new_client(app) as c:
        yield c


async def _authenticate(c: AsyncClient, email: str) -> None:
    await c.post("/auth/register", json={"email": email, "password": PWD})
    resp = await c.post("/auth/login", data={"username": email, "password": PWD})
    c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"


@pytest_asyncio.fixture
async def member_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with _new_client(app) as c:
        await _authenticate(c, "member@test.co")
        yield c


@pytest_asyncio.fixture
async def admin_client(
    app: FastAPI, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncClient]:
    async with _new_client(app) as c:
        await c.post("/auth/register", json={"email": "admin@test.co", "password": PWD})
        async with session_factory() as s:
            await s.execute(
                update(UserRow).where(UserRow.email == "admin@test.co").values(role=UserRole.admin)
            )
            await s.commit()
        resp = await c.post("/auth/login", data={"username": "admin@test.co", "password": PWD})
        c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
