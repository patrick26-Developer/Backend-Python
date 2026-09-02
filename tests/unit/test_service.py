"""Tests unitaires de la couche service — sans HTTP, avec un faux repository.

Montre que le service se teste **sans FastAPI ni base de données** : il suffit de
lui passer n'importe quel objet respectant le `Protocol` TaskRepository.
"""

from __future__ import annotations

from datetime import UTC, datetime

from taskman.schemas import TaskCreate, TaskFilters, TaskRead, TaskStatus, TaskUpdate
from taskman.services import TaskService


class FakeTaskRepository:
    """Faux minimal : suit les appels, se comporte de façon prévisible."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._store: dict[int, TaskRead] = {}
        self._seq = 0

    def create(self, data: TaskCreate) -> TaskRead:
        self.calls.append("create")
        self._seq += 1
        now = datetime.now(UTC)
        task = TaskRead(
            id=self._seq,
            status=TaskStatus.todo,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self._store[task.id] = task
        return task

    def get(self, task_id: int) -> TaskRead | None:
        self.calls.append("get")
        return self._store.get(task_id)

    def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]:
        self.calls.append("list")
        rows = list(self._store.values())
        return rows[filters.offset : filters.offset + filters.limit], len(rows)

    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        self.calls.append("update")
        return self._store.get(task_id)

    def delete(self, task_id: int) -> bool:
        self.calls.append("delete")
        return self._store.pop(task_id, None) is not None


def _service() -> tuple[TaskService, FakeTaskRepository]:
    fake = FakeTaskRepository()
    return TaskService(fake), fake


def test_create_delegates_to_repository() -> None:
    service, fake = _service()
    task = service.create(TaskCreate(title="x", project_id=1))
    assert task.id == 1
    assert fake.calls == ["create"]


def test_list_wraps_result_in_page() -> None:
    service, _ = _service()
    service.create(TaskCreate(title="a", project_id=1))
    service.create(TaskCreate(title="b", project_id=1))
    page = service.list(TaskFilters(limit=1))
    assert page.total == 2
    assert page.limit == 1
    assert len(page.items) == 1


def test_get_missing_returns_none() -> None:
    service, fake = _service()
    assert service.get(42) is None
    assert fake.calls == ["get"]


def test_delete_reports_boolean() -> None:
    service, _ = _service()
    created = service.create(TaskCreate(title="x", project_id=1))
    assert service.delete(created.id) is True
    assert service.delete(created.id) is False
