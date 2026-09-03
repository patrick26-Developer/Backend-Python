"""Tests d'intégration : inscription, connexion, refresh, RBAC, isolation des données."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

PWD = "password-de-test-12345"


def _fresh(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _signup(c: AsyncClient, email: str) -> dict:
    await c.post("/v1/auth/register", json={"email": email, "password": PWD})
    r = await c.post("/v1/auth/login", data={"username": email, "password": PWD})
    return r.json()


# --- inscription / connexion --------------------------------
async def test_register_returns_user_without_password(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/register", json={"email": "u@x.co", "password": PWD})
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "u@x.co"
    assert body["role"] == "member"
    assert "password" not in body and "hashed_password" not in body


async def test_register_duplicate_email_is_409(client: AsyncClient) -> None:
    await client.post("/v1/auth/register", json={"email": "dup@x.co", "password": PWD})
    r = await client.post("/v1/auth/register", json={"email": "dup@x.co", "password": PWD})
    assert r.status_code == 409
    assert r.json()["code"] == "email_already_registered"


async def test_register_weak_password_is_422(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/register", json={"email": "w@x.co", "password": "short"})
    assert r.status_code == 422


async def test_login_wrong_password_is_401(client: AsyncClient) -> None:
    await client.post("/v1/auth/register", json={"email": "l@x.co", "password": PWD})
    r = await client.post("/v1/auth/login", data={"username": "l@x.co", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


async def test_login_unknown_user_is_401(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/login", data={"username": "ghost@x.co", "password": PWD})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"  # même code -> pas d'énumération


async def test_me_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/v1/auth/me")).status_code == 401


async def test_me_returns_current_user(member_client: AsyncClient) -> None:
    r = await member_client.get("/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "member@test.co"


# --- refresh + rotation ------------------------------------
async def test_refresh_rotates_token(client: AsyncClient) -> None:
    tokens = await _signup(client, "r@x.co")
    old_refresh = tokens["refresh_token"]

    r1 = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh != old_refresh

    # l'ancien refresh token ne fonctionne plus (rotation)
    r2 = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401
    assert r2.json()["code"] == "invalid_token"


async def test_access_token_rejected_on_refresh_endpoint(client: AsyncClient) -> None:
    tokens = await _signup(client, "t@x.co")
    r = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401  # mauvais "type" de jeton


# --- RBAC -------------------------------------------------
async def test_admin_route_forbidden_for_member(member_client: AsyncClient) -> None:
    r = await member_client.get("/v1/admin/users")
    assert r.status_code == 403
    assert r.json()["code"] == "permission_denied"


async def test_admin_route_ok_for_admin(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/v1/admin/users")
    assert r.status_code == 200
    assert any(u["email"] == "admin@test.co" for u in r.json())


# --- isolation des données (BOLA / OWASP #1) --------------
async def _as(app: FastAPI, email: str) -> AsyncClient:
    c = _fresh(app)
    tokens = await _signup(c, email)
    c.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    return c


async def test_member_cannot_touch_another_members_task(app: FastAPI) -> None:
    alice = await _as(app, "alice@x.co")
    bob = await _as(app, "bob@x.co")
    try:
        pid = (await alice.post("/v1/projects", json={"name": "secret"})).json()["id"]
        tid = (await alice.post("/v1/tasks", json={"title": "privé", "project_id": pid})).json()[
            "id"
        ]

        # Bob : 404 (et NON 403) — on ne révèle pas l'existence de la ressource
        assert (await bob.get(f"/v1/tasks/{tid}")).status_code == 404
        assert (await bob.patch(f"/v1/tasks/{tid}", json={"status": "done"})).status_code == 404
        assert (await bob.delete(f"/v1/tasks/{tid}")).status_code == 404
        assert (await bob.get("/v1/tasks")).json()["total"] == 0
        assert (await bob.get(f"/v1/projects/{pid}")).status_code == 404

        # Alice voit la sienne
        assert (await alice.get(f"/v1/tasks/{tid}")).status_code == 200
    finally:
        await alice.aclose()
        await bob.aclose()


async def test_admin_sees_every_task(app: FastAPI, admin_client: AsyncClient) -> None:
    member = await _as(app, "someone@x.co")
    try:
        pid = (await member.post("/v1/projects", json={"name": "P"})).json()["id"]
        (await member.post("/v1/tasks", json={"title": "t", "project_id": pid}))
        # l'admin (fixture) voit la tâche du membre
        page = (await admin_client.get("/v1/tasks")).json()
        assert page["total"] == 1
        assert page["items"][0]["title"] == "t"
    finally:
        await member.aclose()
