"""Tests de la solution du Module 06 — auth, RBAC, isolation des données."""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taskman.core.config import Settings
from taskman.core.exceptions import InvalidCredentialsError, InvalidTokenError
from taskman.core.security import create_token, decode_token, hash_password, verify_password
from taskman.repositories import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
    NullUnitOfWork,
)
from taskman.schemas import UserCreate
from taskman.services import AuthService

PWD = "password-de-test-12345"
SECRET = "solution-test-secret-at-least-32-bytes"


# --- crypto (vrai argon2 / vrai JWT) --------------------------
def test_password_hash_is_not_reversible() -> None:
    h = hash_password("s3cr3t-passphrase")
    assert "s3cr3t" not in h
    assert verify_password("s3cr3t-passphrase", h)
    assert not verify_password("autre", h)


def test_jwt_tamper_and_expiry() -> None:
    token, _ = create_token(
        subject="1",
        token_type="access",
        secret=SECRET,
        algorithm="HS256",
        expires_in=timedelta(minutes=1),
    )
    assert decode_token(token, secret=SECRET, algorithms=["HS256"])["sub"] == "1"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token + "x", secret=SECRET, algorithms=["HS256"])
    expired, _ = create_token(
        subject="1",
        token_type="access",
        secret=SECRET,
        algorithm="HS256",
        expires_in=timedelta(seconds=-1),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired, secret=SECRET, algorithms=["HS256"])


# --- AuthService (repos mémoire) --------------------------
def _auth() -> AuthService:
    return AuthService(
        InMemoryUserRepository(),
        InMemoryRefreshTokenRepository(),
        NullUnitOfWork(),
        Settings(env="test", jwt_secret_key=SECRET),  # type: ignore[arg-type]
    )


async def test_login_enumeration_resistant() -> None:
    auth = _auth()
    await auth.register(UserCreate(email="a@x.co", password=PWD))
    with pytest.raises(InvalidCredentialsError):
        await auth.login(email="a@x.co", password="wrong")
    with pytest.raises(InvalidCredentialsError):  # même erreur pour un compte inconnu
        await auth.login(email="ghost@x.co", password="wrong")


async def test_refresh_rotation() -> None:
    auth = _auth()
    await auth.register(UserCreate(email="r@x.co", password=PWD))
    pair = await auth.login(email="r@x.co", password=PWD)
    new = await auth.refresh(pair.refresh_token)
    assert new.refresh_token != pair.refresh_token
    with pytest.raises(InvalidTokenError):
        await auth.refresh(pair.refresh_token)  # ancien révoqué


# --- API : RBAC + isolation ------------------------------
async def _as(app: FastAPI, email: str) -> AsyncClient:
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await c.post("/auth/register", json={"email": email, "password": PWD})
    r = await c.post("/auth/login", data={"username": email, "password": PWD})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c


async def test_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/tasks")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


async def test_rbac(member_client: AsyncClient, admin_client: AsyncClient) -> None:
    assert (await member_client.get("/admin/users")).status_code == 403
    assert (await admin_client.get("/admin/users")).status_code == 200


async def test_data_isolation_returns_404(app: FastAPI) -> None:
    alice = await _as(app, "alice@x.co")
    bob = await _as(app, "bob@x.co")
    try:
        pid = (await alice.post("/projects", json={"name": "P"})).json()["id"]
        tid = (await alice.post("/tasks", json={"title": "x", "project_id": pid})).json()["id"]
        assert (await bob.get(f"/tasks/{tid}")).status_code == 404
        assert (await bob.delete(f"/tasks/{tid}")).status_code == 404
        assert (await bob.get("/tasks")).json()["total"] == 0
        assert (await alice.get(f"/tasks/{tid}")).status_code == 200
    finally:
        await alice.aclose()
        await bob.aclose()
