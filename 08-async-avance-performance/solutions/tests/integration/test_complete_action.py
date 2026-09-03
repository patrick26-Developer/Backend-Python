"""L'action métier `POST /tasks/{id}/complete` — développée en TDD (Module 07).

Historique git : ces tests ont été écrits AVANT l'implémentation.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.factories import task_payload


async def _project(client: AsyncClient) -> int:
    return (await client.post("/projects", json={"name": "P"})).json()["id"]


async def test_complete_sets_status_and_timestamp(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    tid = (await member_client.post("/tasks", json=task_payload(project_id=pid))).json()["id"]

    before = await member_client.get(f"/tasks/{tid}")
    assert before.json()["status"] == "todo"
    assert before.json()["completed_at"] is None

    resp = await member_client.post(f"/tasks/{tid}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["completed_at"] is not None
    assert body["is_overdue"] is False


async def test_complete_is_persisted(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    tid = (await member_client.post("/tasks", json=task_payload(project_id=pid))).json()["id"]
    await member_client.post(f"/tasks/{tid}/complete")
    again = await member_client.get(f"/tasks/{tid}")
    assert again.json()["status"] == "done"
    assert again.json()["completed_at"] is not None


async def test_complete_missing_task_is_404(member_client: AsyncClient) -> None:
    resp = await member_client.post("/tasks/999/complete")
    assert resp.status_code == 404
    assert resp.json()["code"] == "task_not_found"


async def test_complete_requires_auth(client: AsyncClient) -> None:
    assert (await client.post("/tasks/1/complete")).status_code == 401


async def test_cannot_complete_another_users_task(app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport

    async def _as(email: str) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        await c.post("/auth/register", json={"email": email, "password": "password-de-test-12345"})
        r = await c.post(
            "/auth/login", data={"username": email, "password": "password-de-test-12345"}
        )
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        return c

    alice = await _as("a@x.co")
    bob = await _as("b@x.co")
    try:
        pid = (await alice.post("/projects", json={"name": "P"})).json()["id"]
        tid = (await alice.post("/tasks", json=task_payload(project_id=pid))).json()["id"]
        assert (await bob.post(f"/tasks/{tid}/complete")).status_code == 404
    finally:
        await alice.aclose()
        await bob.aclose()
