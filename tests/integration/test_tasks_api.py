"""Tests d'intégration de l'API HTTP (Module 04 : async + base de données)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

FUTURE = (datetime.now(UTC) + timedelta(days=3)).isoformat()
PAST = "2000-01-01T00:00:00Z"


async def _project(client: AsyncClient, name: str = "P") -> int:
    resp = await client.post("/projects", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create(client: AsyncClient, project_id: int, **over: object) -> dict:
    body = {"title": "Tâche", "project_id": project_id, **over}
    resp = await client.post("/tasks", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- meta ---------------------------------------------------------
async def test_root_and_routers(client: AsyncClient) -> None:
    assert (await client.get("/")).json()["env"] == "test"
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert {"/tasks", "/projects", "/projects/{project_id}"} <= set(paths)


# --- création & persistance -------------------------------------
async def test_create_persists_across_requests(client: AsyncClient) -> None:
    pid = await _project(client)
    created = await _create(client, pid, title="persiste")
    fetched = await client.get(f"/tasks/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "persiste"


async def test_create_returns_location_and_defaults(client: AsyncClient) -> None:
    pid = await _project(client)
    resp = await client.post("/tasks", json={"title": "x", "project_id": pid})
    body = resp.json()
    assert resp.headers["location"] == f"/tasks/{body['id']}"
    assert body["status"] == "todo"
    assert body["is_overdue"] is False


async def test_create_unknown_project_gives_clean_404(client: AsyncClient) -> None:
    # L'IntegrityError (FK) est traduite en ProjectNotFoundError par le repository,
    # puis en 404 Problem Details par le handler central.
    resp = await client.post("/tasks", json={"title": "x", "project_id": 999})
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "project_not_found"
    assert resp.headers["content-type"] == "application/problem+json"


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
async def test_create_rejects_invalid(client: AsyncClient, payload: dict) -> None:
    pid = await _project(client)
    assert (await client.post("/tasks", json={**payload, "project_id": pid})).status_code == 422


# --- PATCH ------------------------------------------------------
async def test_patch_partial_and_null(client: AsyncClient) -> None:
    pid = await _project(client)
    created = await _create(client, pid, description="d", priority=2)
    noop = await client.patch(f"/tasks/{created['id']}", json={})
    assert noop.json()["description"] == "d"
    cleared = await client.patch(f"/tasks/{created['id']}", json={"description": None})
    assert cleared.json()["description"] is None
    done = await client.patch(f"/tasks/{created['id']}", json={"status": "done"})
    assert done.json()["status"] == "done" and done.json()["priority"] == 2


async def test_patch_title_null_is_422(client: AsyncClient) -> None:
    pid = await _project(client)
    created = await _create(client, pid)
    assert (await client.patch(f"/tasks/{created['id']}", json={"title": None})).status_code == 422


async def test_patch_missing_is_404(client: AsyncClient) -> None:
    assert (await client.patch("/tasks/999", json={"status": "done"})).status_code == 404


# --- format d'erreur unifié + request-id ----------------------
async def test_error_format_is_problem_details(client: AsyncClient) -> None:
    resp = await client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert set(body) >= {"type", "title", "status", "detail", "code", "instance", "request_id"}
    assert body["code"] == "task_not_found"
    assert body["instance"] == "/tasks/999"


async def test_validation_error_uses_same_format(client: AsyncClient) -> None:
    pid = await _project(client)
    resp = await client.post("/tasks", json={"title": "", "project_id": pid})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["errors"], list)


async def test_request_id_echoed_and_respected(client: AsyncClient) -> None:
    # généré si absent
    r1 = await client.get("/tasks")
    assert r1.headers.get("x-request-id")
    # respecté si fourni
    r2 = await client.get("/tasks", headers={"X-Request-ID": "abc-123"})
    assert r2.headers["x-request-id"] == "abc-123"


# --- liste / filtres ------------------------------------------
async def test_list_filters(client: AsyncClient) -> None:
    p1 = await _project(client, "P1")
    p2 = await _project(client, "P2")
    await _create(client, p1, title="doc archi", priority=5)
    await _create(client, p2, title="autre", priority=1)
    page = (
        await client.get("/tasks", params={"q": "doc", "min_priority": 3, "project_id": p1})
    ).json()
    assert [t["title"] for t in page["items"]] == ["doc archi"]


async def test_list_unknown_query_param_is_422(client: AsyncClient) -> None:
    assert (await client.get("/tasks", params={"statuss": "done"})).status_code == 422


# --- suppression + transaction --------------------------------
async def test_delete_then_404(client: AsyncClient) -> None:
    pid = await _project(client)
    created = await _create(client, pid)
    assert (await client.delete(f"/tasks/{created['id']}")).status_code == 204
    assert (await client.delete(f"/tasks/{created['id']}")).status_code == 404


async def test_isolation_between_tests(client: AsyncClient) -> None:
    # base neuve : aucune tâche d'un test précédent
    assert (await client.get("/tasks")).json()["total"] == 0


# --- projets : task_count sans N+1 ---------------------------
async def test_projects_list_with_task_count(client: AsyncClient) -> None:
    p1 = await _project(client, "P1")
    await _project(client, "P2")
    await _create(client, p1)
    await _create(client, p1)
    page = (await client.get("/projects")).json()
    counts = {p["name"]: p["task_count"] for p in page["items"]}
    assert counts == {"P1": 2, "P2": 0}
