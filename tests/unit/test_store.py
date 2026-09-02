"""Tests unitaires du store — sans HTTP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from taskman.models import TaskCreate, TaskStatus, TaskUpdate
from taskman.store import InMemoryTaskStore


def _store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


def test_create_assigns_incrementing_ids() -> None:
    s = _store()
    a = s.create(TaskCreate(title="a"))
    b = s.create(TaskCreate(title="b"))
    assert (a.id, b.id) == (1, 2)
    assert a.status is TaskStatus.todo
    assert a.created_at.tzinfo is not None


def test_get_missing_returns_none() -> None:
    assert _store().get(123) is None


def test_list_filters_by_status_and_priority() -> None:
    s = _store()
    s.create(TaskCreate(title="low", priority=1))
    s.create(TaskCreate(title="high", priority=5))
    rows, total = s.list(min_priority=3)
    assert total == 1
    assert [t.title for t in rows] == ["high"]


def test_list_sort_and_pagination() -> None:
    s = _store()
    for i in range(5):
        s.create(TaskCreate(title=f"t{i}", priority=i + 1))
    rows, total = s.list(sort="-priority", limit=2, offset=0)
    assert total == 5
    assert [t.title for t in rows] == ["t4", "t3"]


def test_update_is_partial_and_bumps_updated_at() -> None:
    s = _store()
    created = s.create(TaskCreate(title="orig", priority=2))
    updated = s.update(created.id, TaskUpdate(status=TaskStatus.done))
    assert updated is not None
    assert updated.title == "orig"
    assert updated.priority == 2
    assert updated.status is TaskStatus.done
    assert updated.updated_at >= created.updated_at
    assert updated.created_at == created.created_at


def test_update_empty_patch_is_noop() -> None:
    s = _store()
    created = s.create(TaskCreate(title="orig"))
    same = s.update(created.id, TaskUpdate())
    assert same == created


def test_update_missing_returns_none() -> None:
    assert _store().update(999, TaskUpdate(title="x")) is None


def test_delete_reports_presence() -> None:
    s = _store()
    created = s.create(TaskCreate(title="x"))
    assert s.delete(created.id) is True
    assert s.delete(created.id) is False


def test_due_date_future_accepted() -> None:
    s = _store()
    due = datetime.now(UTC) + timedelta(days=1)
    task = s.create(TaskCreate(title="x", due_date=due))
    assert task.due_date == due
