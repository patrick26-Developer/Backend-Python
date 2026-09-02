"""Tests unitaires du store — sans HTTP (Module 02)."""

from __future__ import annotations

from decimal import Decimal

from taskman.models import ChecklistItem, TaskCreate, TaskFilters, TaskStatus, TaskUpdate
from taskman.store import InMemoryTaskStore


def _store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


def _new(**over: object) -> TaskCreate:
    base: dict[str, object] = {"title": "Tâche", "project_id": 1}
    return TaskCreate(**{**base, **over})  # type: ignore[arg-type]


def test_create_assigns_ids_and_defaults() -> None:
    s = _store()
    a = s.create(_new(title="a"))
    b = s.create(_new(title="b"))
    assert (a.id, b.id) == (1, 2)
    assert a.status is TaskStatus.todo
    assert a.project_id == 1
    assert a.created_at.tzinfo is not None
    assert a.is_overdue is False


def test_created_task_is_never_overdue() -> None:
    # On ne peut pas CRÉER une tâche déjà en retard (règle métier "échéance future").
    # Le calcul complet de `is_overdue` est couvert dans tests/unit/test_models.py.
    assert _store().create(_new(title="x")).is_overdue is False


def test_list_filters_combine() -> None:
    s = _store()
    s.create(_new(title="doc haute", priority=5, project_id=1))
    s.create(_new(title="autre", priority=1, project_id=2))
    s.create(_new(title="doc basse", priority=2, project_id=1))

    rows, total = s.list(TaskFilters(q="doc", min_priority=2, project_id=1))
    assert total == 2
    assert {t.title for t in rows} == {"doc haute", "doc basse"}


def test_list_search_covers_description() -> None:
    s = _store()
    s.create(_new(title="rien", description="contient PostgreSQL"))
    _, total = s.list(TaskFilters(q="postgresql"))
    assert total == 1


def test_list_pagination_and_sort() -> None:
    s = _store()
    for i in range(5):
        s.create(_new(title=f"t{i}", priority=i + 1))
    rows, total = s.list(TaskFilters(sort="-priority", limit=2))
    assert total == 5
    assert [t.title for t in rows] == ["t4", "t3"]


def test_update_partial_and_bumps_updated_at() -> None:
    s = _store()
    created = s.create(_new(title="orig", priority=2))
    updated = s.update(created.id, TaskUpdate(status=TaskStatus.done))
    assert updated is not None
    assert updated.title == "orig"
    assert updated.priority == 2
    assert updated.status is TaskStatus.done
    assert updated.updated_at >= created.updated_at
    assert updated.created_at == created.created_at


def test_update_empty_patch_is_noop() -> None:
    s = _store()
    created = s.create(_new())
    assert s.update(created.id, TaskUpdate()) == created


def test_update_null_clears_description() -> None:
    s = _store()
    created = s.create(_new(description="à effacer"))
    updated = s.update(created.id, TaskUpdate(description=None))
    assert updated is not None and updated.description is None


def test_update_replaces_checklist() -> None:
    s = _store()
    created = s.create(_new(checklist=[ChecklistItem(label="ancien")]))
    updated = s.update(
        created.id, TaskUpdate(checklist=[ChecklistItem(label="nouveau", done=True)])
    )
    assert updated is not None
    assert [(c.label, c.done) for c in updated.checklist] == [("nouveau", True)]


def test_update_missing_returns_none() -> None:
    assert _store().update(999, TaskUpdate(title="x")) is None


def test_delete_reports_presence() -> None:
    s = _store()
    created = s.create(_new())
    assert s.delete(created.id) is True
    assert s.delete(created.id) is False


def test_decimal_estimate_is_not_float() -> None:
    s = _store()
    t = s.create(_new(estimate_hours=Decimal("2.5")))
    assert isinstance(t.estimate_hours, Decimal)
