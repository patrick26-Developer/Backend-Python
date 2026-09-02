"""Tests de la solution du Module 02 (standalone).

Lancer :  pytest 02-modelisation-et-validation/solutions/test_solution.py
La vraie suite du projet vit dans tests/ à la racine.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from .main import app, store
from .models import TaskCreate, TaskRead, TaskStatus, TaskUpdate

FUTURE = (datetime.now(UTC) + timedelta(days=3)).isoformat()
PAST_DT = datetime.now(UTC) - timedelta(days=3)


@pytest.fixture
def client() -> Iterator[TestClient]:
    store.clear()
    with TestClient(app) as c:
        yield c


def _create(c: TestClient, **over: object) -> dict[str, object]:
    r = c.post("/tasks", json={"title": "T", "project_id": 1, **over})
    assert r.status_code == 201, r.text
    body: dict[str, object] = r.json()
    return body


# --- séparation des schémas ------------------------------------------
def test_project_id_required_on_create_only(client: TestClient) -> None:
    assert client.post("/tasks", json={"title": "x"}).status_code == 422
    created = _create(client)
    # project_id ignoré sur PATCH (extra="ignore" par défaut sur TaskUpdate)
    r = client.patch(f"/tasks/{created['id']}", json={"project_id": 99})
    assert r.status_code == 200 and r.json()["project_id"] == 1


def test_server_fields_not_client_settable(client: TestClient) -> None:
    body = _create(client, id=42, is_overdue=True, status="done")
    assert (body["id"], body["is_overdue"], body["status"]) == (1, False, "todo")


# --- PATCH correct ---------------------------------------------------
def test_patch_null_vs_absent(client: TestClient) -> None:
    tid = _create(client, description="d")["id"]
    assert client.patch(f"/tasks/{tid}", json={}).json()["description"] == "d"
    cleared = client.patch(f"/tasks/{tid}", json={"description": None}).json()
    assert cleared["description"] is None


def test_patch_title_null_rejected(client: TestClient) -> None:
    created = _create(client)
    assert client.patch(f"/tasks/{created['id']}", json={"title": None}).status_code == 422


# --- types riches --------------------------------------------------
def test_email_and_decimal_validation(client: TestClient) -> None:
    assert _create(client, estimate_hours="2.5")["estimate_hours"] == "2.5"
    assert (
        client.post(
            "/tasks", json={"title": "x", "project_id": 1, "assignee_email": "bad"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/tasks", json={"title": "x", "project_id": 1, "estimate_hours": "1.005"}
        ).status_code
        == 422
    )


# --- modèle imbriqué ---------------------------------------------
def test_nested_checklist_error_path(client: TestClient) -> None:
    r = client.post("/tasks", json={"title": "x", "project_id": 1, "checklist": [{"label": ""}]})
    assert r.json()["detail"][0]["loc"] == ["body", "checklist", 0, "label"]


# --- query model -------------------------------------------------
def test_unknown_query_param_rejected(client: TestClient) -> None:
    assert client.get("/tasks", params={"statuss": "done"}).status_code == 422


# --- is_overdue au niveau modèle -------------------------------
def _read(**over: object) -> TaskRead:
    base: dict[str, object] = {
        "id": 1,
        "project_id": 1,
        "title": "x",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    return TaskRead.model_validate({**base, **over})


def test_is_overdue_computed() -> None:
    assert _read(due_date=PAST_DT, status=TaskStatus.doing).is_overdue is True
    assert _read(due_date=PAST_DT, status=TaskStatus.done).is_overdue is False
    assert _read().is_overdue is False


def test_create_rejects_past_due_date() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="x", project_id=1, due_date=PAST_DT)


def test_update_past_due_date_when_provided() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(due_date=PAST_DT)
    assert TaskUpdate(estimate_hours=Decimal("1.00")).due_date is None
