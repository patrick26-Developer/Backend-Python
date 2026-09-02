"""Tests d'intégration : l'API HTTP de bout en bout (Module 02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

FUTURE = (datetime.now(UTC) + timedelta(days=3)).isoformat()
PAST = "2000-01-01T00:00:00Z"


def _create(client: TestClient, **over: object) -> dict:
    body = {"title": "Tâche", "project_id": 1, **over}
    resp = client.post("/tasks", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_meta_endpoints(client: TestClient) -> None:
    assert client.get("/").json()["name"] == "taskman"
    assert client.get("/health").json() == {"status": "ok"}


# --- création ---------------------------------------------------------
def test_create_returns_201_with_location(client: TestClient) -> None:
    resp = client.post("/tasks", json={"title": "écrire", "project_id": 2})
    assert resp.status_code == 201
    body = resp.json()
    assert body["project_id"] == 2
    assert body["status"] == "todo"
    assert body["is_overdue"] is False
    assert resp.headers["location"] == f"/tasks/{body['id']}"


def test_create_without_project_id_is_422(client: TestClient) -> None:
    assert client.post("/tasks", json={"title": "x"}).status_code == 422


def test_server_fields_cannot_be_set_by_client(client: TestClient) -> None:
    body = _create(client, id=999, is_overdue=True, created_at=PAST, status="done")
    assert body["id"] == 1
    assert body["is_overdue"] is False
    assert body["status"] == "todo"
    assert body["created_at"] != PAST


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   ", "project_id": 1},
        {"title": "x", "project_id": 1, "priority": 6},
        {"title": "x", "project_id": 1, "due_date": PAST},
        {"title": "x", "project_id": 1, "assignee_email": "nope"},
        {"title": "x", "project_id": 1, "estimate_hours": "1.005"},
        {"title": "x", "project_id": 1, "checklist": [{"label": "  "}]},
        {"title": "x", "project_id": 0},
    ],
)
def test_create_rejects_invalid(client: TestClient, payload: dict) -> None:
    assert client.post("/tasks", json=payload).status_code == 422


def test_nested_error_path(client: TestClient) -> None:
    resp = client.post("/tasks", json={"title": "x", "project_id": 1, "checklist": [{"label": ""}]})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["body", "checklist", 0, "label"]


# --- PATCH ------------------------------------------------------------
def test_patch_empty_is_noop(client: TestClient) -> None:
    created = _create(client, description="garde-moi")
    body = client.patch(f"/tasks/{created['id']}", json={}).json()
    assert body["description"] == "garde-moi"
    assert body["updated_at"] == created["updated_at"]


def test_patch_null_clears_description(client: TestClient) -> None:
    created = _create(client, description="à effacer")
    body = client.patch(f"/tasks/{created['id']}", json={"description": None}).json()
    assert body["description"] is None


def test_patch_empty_tags_clears(client: TestClient) -> None:
    created = _create(client, tags=["a", "b"])
    body = client.patch(f"/tasks/{created['id']}", json={"tags": []}).json()
    assert body["tags"] == []


def test_patch_title_null_is_422(client: TestClient) -> None:
    created = _create(client)
    assert client.patch(f"/tasks/{created['id']}", json={"title": None}).status_code == 422


def test_patch_due_date_null_recomputes_overdue(client: TestClient) -> None:
    created = _create(client, due_date=FUTURE)
    body = client.patch(f"/tasks/{created['id']}", json={"due_date": None}).json()
    assert body["due_date"] is None
    assert body["is_overdue"] is False


def test_patch_missing_is_404(client: TestClient) -> None:
    assert client.patch("/tasks/999", json={"status": "done"}).status_code == 404


# --- liste / filtres -------------------------------------------------
def test_list_pagination_metadata(client: TestClient) -> None:
    for i in range(3):
        _create(client, title=f"t{i}", priority=i + 1)
    page = client.get("/tasks", params={"limit": 2}).json()
    assert page["total"] == 3 and page["limit"] == 2 and len(page["items"]) == 2


def test_list_unknown_query_param_is_422(client: TestClient) -> None:
    assert client.get("/tasks", params={"statuss": "done"}).status_code == 422


def test_list_search_and_filters_combine(client: TestClient) -> None:
    _create(client, title="doc archi", priority=5, project_id=1)
    _create(client, title="autre", priority=1, project_id=2)
    page = client.get("/tasks", params={"q": "doc", "min_priority": 3, "project_id": 1}).json()
    assert [t["title"] for t in page["items"]] == ["doc archi"]


# --- suppression ---------------------------------------------------
def test_delete_is_204_then_404(client: TestClient) -> None:
    created = _create(client)
    assert client.delete(f"/tasks/{created['id']}").status_code == 204
    assert client.delete(f"/tasks/{created['id']}").status_code == 404


# --- contrat OpenAPI ---------------------------------------------------
def test_openapi_separates_input_output(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert any("TaskCreate" in name for name in schemas)
    assert any("TaskRead" in name for name in schemas)


def test_estimate_hours_serialized_as_string(client: TestClient) -> None:
    body = _create(client, estimate_hours="2.5")
    assert body["estimate_hours"] == "2.5"
