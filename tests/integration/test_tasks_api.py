"""Tests d'intégration : l'API HTTP de bout en bout (store en mémoire)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

FUTURE = (datetime.now(UTC) + timedelta(days=3)).isoformat()


def _create(client: TestClient, **over: object) -> dict[str, object]:
    resp = client.post("/tasks", json={"title": "Tâche", **over})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_meta_endpoints(client: TestClient) -> None:
    assert client.get("/").json()["name"] == "taskman"
    assert client.get("/health").json() == {"status": "ok"}


def test_create_returns_201_with_location_header(client: TestClient) -> None:
    resp = client.post("/tasks", json={"title": "écrire les tests", "priority": 4})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["status"] == "todo"
    assert resp.headers["location"] == f"/tasks/{body['id']}"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   "},
        {"title": "x", "priority": 0},
        {"title": "x", "priority": 6},
        {"title": "x", "tags": ["t" + str(i) for i in range(11)]},
        {"title": "x", "due_date": "2000-01-01T00:00:00Z"},
    ],
)
def test_create_rejects_invalid(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/tasks", json=payload).status_code == 422


def test_get_missing_returns_404(client: TestClient) -> None:
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_get_invalid_id_returns_422(client: TestClient) -> None:
    assert client.get("/tasks/-1").status_code == 422


def test_list_pagination_metadata(client: TestClient) -> None:
    for i in range(3):
        _create(client, title=f"t{i}", priority=i + 1)
    page = client.get("/tasks", params={"limit": 2}).json()
    assert page["total"] == 3
    assert page["limit"] == 2
    assert len(page["items"]) == 2


def test_list_status_filter(client: TestClient) -> None:
    a = _create(client, title="a")
    _create(client, title="b")
    client.patch(f"/tasks/{a['id']}", json={"status": "done"})
    page = client.get("/tasks", params={"status": "done"}).json()
    assert [t["title"] for t in page["items"]] == ["a"]


def test_patch_partial_update(client: TestClient) -> None:
    created = _create(client, title="original", priority=2)
    resp = client.patch(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["title"] == "original"
    assert body["priority"] == 2
    assert body["created_at"] == created["created_at"]


def test_patch_missing_returns_404(client: TestClient) -> None:
    assert client.patch("/tasks/999", json={"status": "done"}).status_code == 404


def test_delete_is_204_then_404(client: TestClient) -> None:
    created = _create(client)
    assert client.delete(f"/tasks/{created['id']}").status_code == 204
    assert client.delete(f"/tasks/{created['id']}").status_code == 404


def test_openapi_contract(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/tasks", "/tasks/{task_id}"} <= set(paths)
