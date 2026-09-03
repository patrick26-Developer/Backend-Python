"""Tests d'intégration des fonctionnalités du Module 08 :
cache + invalidation, pagination cursor, export streamé, tâche de fond."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from tests.factories import task_payload


async def _project(client: AsyncClient, name: str = "P") -> int:
    return (await client.post("/v1/projects", json={"name": name})).json()["id"]


# --- stats + cache -----------------------------------------
async def test_project_stats(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    t1 = (await member_client.post("/v1/tasks", json=task_payload(project_id=pid))).json()["id"]
    await member_client.post("/v1/tasks", json=task_payload(project_id=pid))
    await member_client.post(f"/v1/tasks/{t1}/complete")

    stats = (await member_client.get(f"/v1/projects/{pid}/stats")).json()
    assert stats["total"] == 2
    assert stats["by_status"]["done"] == 1
    assert stats["completion_rate"] == 0.5


async def test_stats_of_unknown_project_is_404(member_client: AsyncClient) -> None:
    assert (await member_client.get("/v1/projects/999/stats")).status_code == 404


async def test_stats_cache_invalidated_on_new_task(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    await member_client.post("/v1/tasks", json=task_payload(project_id=pid))
    assert (await member_client.get(f"/v1/projects/{pid}/stats")).json()["total"] == 1
    await member_client.post("/v1/tasks", json=task_payload(project_id=pid))
    # sans invalidation, on lirait encore "1" depuis le cache
    assert (await member_client.get(f"/v1/projects/{pid}/stats")).json()["total"] == 2


# --- pagination cursor ------------------------------------
async def test_cursor_pagination(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    for _ in range(5):
        await member_client.post("/v1/tasks", json=task_payload(project_id=pid))

    seen: set[int] = set()
    params: dict[str, object] = {"limit": 2, "sort": "-created_at"}
    for _ in range(10):
        page = (await member_client.get("/v1/tasks", params=params)).json()
        seen.update(t["id"] for t in page["items"])
        if not page["next_cursor"]:
            break
        params = {"limit": 2, "sort": "-created_at", "cursor": page["next_cursor"]}

    assert len(seen) == 5


async def test_bad_cursor_is_400(member_client: AsyncClient) -> None:
    resp = await member_client.get("/v1/tasks", params={"cursor": "pas-du-base64-valide!!"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "bad_request"


# --- export NDJSON --------------------------------------
async def test_export_ndjson_streamed(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    for i in range(3):
        await member_client.post(
            "/v1/tasks", json=task_payload(project_id=pid, title=f"export {i}")
        )

    resp = await member_client.get("/v1/tasks/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    lines = [line for line in resp.text.splitlines() if line]
    assert len(lines) == 3
    assert all("title" in json.loads(line) for line in lines)


async def test_export_only_own_tasks(app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport

    async def _as(email: str) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        await c.post(
            "/v1/auth/register", json={"email": email, "password": "password-de-test-12345"}
        )
        r = await c.post(
            "/v1/auth/login", data={"username": email, "password": "password-de-test-12345"}
        )
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        return c

    alice = await _as("a@x.co")
    bob = await _as("b@x.co")
    try:
        pid = (await alice.post("/v1/projects", json={"name": "P"})).json()["id"]
        await alice.post("/v1/tasks", json=task_payload(project_id=pid))
        assert len([x for x in (await alice.get("/v1/tasks/export")).text.splitlines() if x]) == 1
        assert (await bob.get("/v1/tasks/export")).text.strip() == ""
    finally:
        await alice.aclose()
        await bob.aclose()


# --- tâche de fond -------------------------------------
async def test_complete_triggers_background_notification(
    member_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []

    async def _spy(self, task):  # type: ignore[no-untyped-def]
        seen.append(task.id)

    from taskman.services.notifications import LoggingNotifier

    monkeypatch.setattr(LoggingNotifier, "task_completed", _spy)

    pid = await _project(member_client)
    tid = (await member_client.post("/v1/tasks", json=task_payload(project_id=pid))).json()["id"]
    await member_client.post(f"/v1/tasks/{tid}/complete")
    assert seen == [tid]
