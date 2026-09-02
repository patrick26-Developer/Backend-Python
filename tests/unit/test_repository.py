"""Tests unitaires de l'implémentation en mémoire du repository — sans HTTP."""

from __future__ import annotations

from decimal import Decimal

from taskman.repositories import InMemoryTaskRepository
from taskman.schemas import ChecklistItem, TaskCreate, TaskFilters, TaskStatus, TaskUpdate


def _repo() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


def _new(**over: object) -> TaskCreate:
    base: dict[str, object] = {"title": "Tâche", "project_id": 1}
    return TaskCreate(**{**base, **over})  # type: ignore[arg-type]


def test_create_assigns_ids_and_defaults() -> None:
    r = _repo()
    a = r.create(_new(title="a"))
    b = r.create(_new(title="b"))
    assert (a.id, b.id) == (1, 2)
    assert a.status is TaskStatus.todo
    assert a.project_id == 1
    assert a.created_at.tzinfo is not None
    assert a.is_overdue is False


def test_get_missing_returns_none() -> None:
    assert _repo().get(123) is None


def test_list_filters_combine() -> None:
    r = _repo()
    r.create(_new(title="doc haute", priority=5, project_id=1))
    r.create(_new(title="autre", priority=1, project_id=2))
    r.create(_new(title="doc basse", priority=2, project_id=1))
    rows, total = r.list(TaskFilters(q="doc", min_priority=2, project_id=1))
    assert total == 2
    assert {t.title for t in rows} == {"doc haute", "doc basse"}


def test_list_search_covers_description() -> None:
    r = _repo()
    r.create(_new(title="rien", description="contient PostgreSQL"))
    _, total = r.list(TaskFilters(q="postgresql"))
    assert total == 1


def test_list_pagination_and_sort() -> None:
    r = _repo()
    for i in range(5):
        r.create(_new(title=f"t{i}", priority=i + 1))
    rows, total = r.list(TaskFilters(sort="-priority", limit=2))
    assert total == 5
    assert [t.title for t in rows] == ["t4", "t3"]


def test_update_partial_and_bumps_updated_at() -> None:
    r = _repo()
    created = r.create(_new(title="orig", priority=2))
    updated = r.update(created.id, TaskUpdate(status=TaskStatus.done))
    assert updated is not None
    assert updated.title == "orig"
    assert updated.priority == 2
    assert updated.status is TaskStatus.done
    assert updated.updated_at >= created.updated_at
    assert updated.created_at == created.created_at


def test_update_empty_patch_is_noop() -> None:
    r = _repo()
    created = r.create(_new())
    assert r.update(created.id, TaskUpdate()) == created


def test_update_null_clears_description() -> None:
    r = _repo()
    created = r.create(_new(description="à effacer"))
    updated = r.update(created.id, TaskUpdate(description=None))
    assert updated is not None and updated.description is None


def test_update_replaces_checklist() -> None:
    r = _repo()
    created = r.create(_new(checklist=[ChecklistItem(label="ancien")]))
    updated = r.update(
        created.id, TaskUpdate(checklist=[ChecklistItem(label="nouveau", done=True)])
    )
    assert updated is not None
    assert [(c.label, c.done) for c in updated.checklist] == [("nouveau", True)]


def test_update_missing_returns_none() -> None:
    assert _repo().update(999, TaskUpdate(title="x")) is None


def test_delete_reports_presence() -> None:
    r = _repo()
    created = r.create(_new())
    assert r.delete(created.id) is True
    assert r.delete(created.id) is False


def test_decimal_estimate_is_not_float() -> None:
    t = _repo().create(_new(estimate_hours=Decimal("2.5")))
    assert isinstance(t.estimate_hours, Decimal)
