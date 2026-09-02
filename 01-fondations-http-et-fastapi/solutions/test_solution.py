"""Tests de la solution du Module 01.

On teste ici la solution *en place* (dossier solutions/). La vraie suite de tests
du projet vit dans `tests/` à la racine et sera étoffée au Module 07.

Lancer :  pytest 01-fondations-http-et-fastapi/solutions/test_solution.py
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from .main import app, store

FUTURE = (datetime.now(UTC) + timedelta(days=3)).isoformat()


@pytest.fixture
def client() -> Iterator[TestClient]:
    store.clear()
    with TestClient(app) as c:
        yield c


def _make(client: TestClient, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"title": "Tâche", "priority": 3} | over
    resp = client.post("/tasks", json=body)
    assert resp.status_code == 201
    result: dict[str, Any] = resp.json()
    return result


# --- meta ------------------------------------------------------------------
def test_root_and_health(client: TestClient) -> None:
    assert client.get("/").json()["name"] == "taskman"
    assert client.get("/health").json() == {"status": "ok"}


# --- create --------------------------------------------------------------
def test_create_returns_201_and_location(client: TestClient) -> None:
    resp = client.post("/tasks", json={"title": "Écrire les tests"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["status"] == "todo"
    assert resp.headers["location"] == f"/tasks/{body['id']}"


def test_create_strips_title(client: TestClient) -> None:
    assert _make(client, title="  espacé  ")["title"] == "espacé"


@pytest.mark.parametrize(
    "bad",
    [
        {"title": "   "},
        {"title": "x", "priority": 0},
        {"title": "x", "priority": 6},
        {"title": "x", "tags": [f"t{i}" for i in range(11)]},
        {"title": "x", "due_date": "2000-01-01T00:00:00Z"},
    ],
)
def test_create_rejects_invalid_payload(client: TestClient, bad: dict[str, object]) -> None:
    assert client.post("/tasks", json=bad).status_code == 422


# --- read / list -------------------------------------------------------
def test_get_missing_is_404(client: TestClient) -> None:
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_get_negative_id_is_422(client: TestClient) -> None:
    assert client.get("/tasks/-1").status_code == 422


def test_list_filters_and_pagination(client: TestClient) -> None:
    _make(client, title="a", priority=5)
    _make(client, title="b", priority=1)
    _make(client, title="c", priority=4)

    page = client.get("/tasks", params={"min_priority": 4}).json()
    assert page["total"] == 2
    assert [t["title"] for t in page["items"]] == ["a", "c"]  # tri -priority

    page2 = client.get("/tasks", params={"limit": 1, "offset": 1}).json()
    assert page2["limit"] == 1 and page2["offset"] == 1
    assert len(page2["items"]) == 1


def test_list_sort_reverses(client: TestClient) -> None:
    _make(client, title="first")
    _make(client, title="second")
    asc = client.get("/tasks", params={"sort": "created_at"}).json()["items"]
    desc = client.get("/tasks", params={"sort": "-created_at"}).json()["items"]
    assert [t["title"] for t in asc] == list(reversed([t["title"] for t in desc]))


# --- update -----------------------------------------------------------
def test_patch_is_partial(client: TestClient) -> None:
    created = _make(client, title="original", priority=2)
    resp = client.patch(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["title"] == "original"  # inchangé
    assert body["priority"] == 2
    assert body["updated_at"] != created["updated_at"]
    assert body["created_at"] == created["created_at"]


def test_patch_missing_is_404(client: TestClient) -> None:
    assert client.patch("/tasks/999", json={"status": "done"}).status_code == 404


# --- delete ---------------------------------------------------------
def test_delete_then_delete_again(client: TestClient) -> None:
    created = _make(client)
    assert client.delete(f"/tasks/{created['id']}").status_code == 204
    assert client.delete(f"/tasks/{created['id']}").status_code == 404


# --- contrat OpenAPI --------------------------------------------------
def test_openapi_lists_task_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/tasks" in paths and "/tasks/{task_id}" in paths
    assert set(paths["/tasks"]) >= {"get", "post"}
