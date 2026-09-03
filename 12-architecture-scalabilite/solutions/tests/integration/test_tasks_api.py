"""Tests d'intégration de l'API HTTP des tâches (authentifiée depuis le Module 06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

FUTURE = (datetime.now(UTC) + timedelta(days=3)).isoformat()
PAST = "2000-01-01T00:00:00Z"


async def _project(client: AsyncClient, name: str = "P") -> int:
    resp = await client.post("/v1/projects", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create(client: AsyncClient, project_id: int, **over: object) -> dict:
    body = {"title": "Tâche", "project_id": project_id, **over}
    resp = await client.post("/v1/tasks", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- authentification requise ----------------------------------
async def test_tasks_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/v1/tasks")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_bad_token_is_401(client: AsyncClient) -> None:
    resp = await client.get("/v1/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_token"


# --- CRUD (authentifié) -------------------------------------
async def test_create_persists(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    created = await _create(member_client, pid, title="persiste")
    fetched = await member_client.get(f"/v1/tasks/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "persiste"


async def test_create_returns_location_and_defaults(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    resp = await member_client.post("/v1/tasks", json={"title": "x", "project_id": pid})
    body = resp.json()
    assert resp.headers["location"] == f"/v1/tasks/{body['id']}"
    assert body["status"] == "todo"
    assert body["is_overdue"] is False


async def test_create_unknown_project_gives_clean_404(member_client: AsyncClient) -> None:
    resp = await member_client.post("/v1/tasks", json={"title": "x", "project_id": 999})
    assert resp.status_code == 404
    assert resp.json()["code"] == "project_not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   "},
        {"title": "x", "priority": 6},
        {"title": "x", "due_date": PAST},
        {"title": "x", "assignee_email": "nope"},
        {"title": "x", "estimate_hours": "1.005"},
        {"title": "x", "checklist": [{"label": "  "}]},
    ],
)
async def test_create_rejects_invalid(member_client: AsyncClient, payload: dict) -> None:
    pid = await _project(member_client)
    resp = await member_client.post("/v1/tasks", json={**payload, "project_id": pid})
    assert resp.status_code == 422


async def test_patch_partial_and_null(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    created = await _create(member_client, pid, description="d", priority=2)
    noop = await member_client.patch(f"/v1/tasks/{created['id']}", json={})
    assert noop.json()["description"] == "d"
    cleared = await member_client.patch(f"/v1/tasks/{created['id']}", json={"description": None})
    assert cleared.json()["description"] is None
    done = await member_client.patch(f"/v1/tasks/{created['id']}", json={"status": "done"})
    assert done.json()["status"] == "done" and done.json()["priority"] == 2


async def test_patch_title_null_is_422(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    created = await _create(member_client, pid)
    resp = await member_client.patch(f"/v1/tasks/{created['id']}", json={"title": None})
    assert resp.status_code == 422


async def test_patch_missing_is_404(member_client: AsyncClient) -> None:
    resp = await member_client.patch("/v1/tasks/999", json={"status": "done"})
    assert resp.status_code == 404


async def test_delete_then_404(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    created = await _create(member_client, pid)
    assert (await member_client.delete(f"/v1/tasks/{created['id']}")).status_code == 204
    assert (await member_client.delete(f"/v1/tasks/{created['id']}")).status_code == 404


async def test_list_filters(member_client: AsyncClient) -> None:
    p1 = await _project(member_client, "P1")
    p2 = await _project(member_client, "P2")
    await _create(member_client, p1, title="doc archi", priority=5)
    await _create(member_client, p2, title="autre", priority=1)
    page = (
        await member_client.get(
            "/v1/tasks", params={"q": "doc", "min_priority": 3, "project_id": p1}
        )
    ).json()
    assert [t["title"] for t in page["items"]] == ["doc archi"]


async def test_list_unknown_query_param_is_422(member_client: AsyncClient) -> None:
    assert (await member_client.get("/v1/tasks", params={"statuss": "done"})).status_code == 422


# --- format d'erreur + request-id ----------------------------
async def test_error_format_is_problem_details(member_client: AsyncClient) -> None:
    resp = await member_client.get("/v1/tasks/999")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert set(body) >= {"type", "title", "status", "detail", "code", "instance", "request_id"}
    assert body["code"] == "task_not_found"


async def test_request_id_echoed_and_respected(member_client: AsyncClient) -> None:
    r1 = await member_client.get("/v1/tasks")
    assert r1.headers.get("x-request-id")
    r2 = await member_client.get("/v1/tasks", headers={"X-Request-ID": "abc-123"})
    assert r2.headers["x-request-id"] == "abc-123"


# --- projets : task_count sans N+1 --------------------------
async def test_projects_list_with_task_count(member_client: AsyncClient) -> None:
    p1 = await _project(member_client, "P1")
    await _project(member_client, "P2")
    await _create(member_client, p1)
    await _create(member_client, p1)
    page = (await member_client.get("/v1/projects")).json()
    counts = {p["name"]: p["task_count"] for p in page["items"]}
    assert counts == {"P1": 2, "P2": 0}
