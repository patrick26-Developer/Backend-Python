"""Tests de la solution du Module 03 — l'accent est mis sur l'ARCHITECTURE :
découpage en couches, injection de dépendances, configuration.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from taskman.core.config import Settings
from taskman.repositories import InMemoryTaskRepository
from taskman.schemas import TaskCreate, TaskFilters
from taskman.services import TaskService


# --- configuration -------------------------------------------------
def test_settings_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.env == "local"
    assert s.docs_url == "/docs"


def test_settings_production_hides_docs() -> None:
    s = Settings(_env_file=None, env="production")  # type: ignore[call-arg]
    assert s.is_production is True
    assert s.docs_url is None


# --- couche service isolée (sans HTTP) --------------------------
def test_service_uses_any_repository_protocol() -> None:
    service = TaskService(InMemoryTaskRepository())
    task = service.create(TaskCreate(title="x", project_id=1))
    page = service.list(TaskFilters())
    assert page.total == 1
    assert page.items[0].id == task.id


# --- injection de dépendances via l'API -------------------------
def test_di_wires_service_to_repository(client: TestClient) -> None:
    client.post("/tasks", json={"title": "a", "project_id": 1})
    assert client.get("/tasks").json()["total"] == 1


def test_override_gives_a_fresh_repository(client: TestClient) -> None:
    # la fixture injecte un repository neuf -> aucun résidu
    assert client.get("/tasks").json()["total"] == 0


def test_config_injected_into_routes(client: TestClient) -> None:
    assert client.get("/").json()["env"] == "test"


def test_routers_mounted_by_domain(client: TestClient) -> None:
    tags = {
        t["name"]
        for path in client.get("/openapi.json").json()["paths"].values()
        for op in path.values()
        for t in [{"name": n} for n in op.get("tags", [])]
    }
    assert {"meta", "tasks"} <= tags


# --- le CRUD marche toujours (non-régression) -----------------
def test_crud_still_works(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "t", "project_id": 1})
    assert created.status_code == 201
    tid = created.json()["id"]
    assert client.get(f"/tasks/{tid}").status_code == 200
    assert client.patch(f"/tasks/{tid}", json={"status": "done"}).json()["status"] == "done"
    assert client.delete(f"/tasks/{tid}").status_code == 204
    assert client.get(f"/tasks/{tid}").status_code == 404
