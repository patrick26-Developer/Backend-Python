"""Tests unitaires de la couche service — sans HTTP, sans base de données.

Repositories **en mémoire** + `NullUnitOfWork`. Le service se teste en isolation
grâce aux `Protocol`. Depuis le Module 05, il **lève** au lieu de renvoyer `None`.
"""

from __future__ import annotations

import pytest

from taskman.core.exceptions import ProjectNotFoundError, TaskNotFoundError
from taskman.repositories import (
    InMemoryProjectRepository,
    InMemoryTaskRepository,
    NullUnitOfWork,
)
from taskman.schemas import ProjectCreate, TaskCreate, TaskFilters, TaskStatus, TaskUpdate
from taskman.services import ProjectService, TaskService


def _task_service() -> tuple[TaskService, InMemoryTaskRepository]:
    repo = InMemoryTaskRepository()
    return TaskService(repo, NullUnitOfWork()), repo


async def test_create_then_list() -> None:
    service, _ = _task_service()
    await service.create(TaskCreate(title="a", project_id=1))
    await service.create(TaskCreate(title="b", project_id=1))
    page = await service.list(TaskFilters(limit=1))
    assert page.total == 2
    assert len(page.items) == 1


async def test_get_missing_raises() -> None:
    service, _ = _task_service()
    with pytest.raises(TaskNotFoundError):
        await service.get(42)


async def test_update_missing_raises() -> None:
    service, _ = _task_service()
    with pytest.raises(TaskNotFoundError):
        await service.update(42, TaskUpdate(status=TaskStatus.done))


async def test_delete_missing_raises() -> None:
    service, _ = _task_service()
    with pytest.raises(TaskNotFoundError):
        await service.delete(42)


async def test_delete_existing_returns_none() -> None:
    service, _ = _task_service()
    created = await service.create(TaskCreate(title="x", project_id=1))
    assert await service.delete(created.id) is None


async def test_commit_called_on_write_not_read() -> None:
    class SpyUoW:
        commits = 0

        async def commit(self) -> None:
            SpyUoW.commits += 1

        async def rollback(self) -> None:  # pragma: no cover
            pass

    service = TaskService(InMemoryTaskRepository(), SpyUoW())
    await service.create(TaskCreate(title="x", project_id=1))
    await service.list(TaskFilters())
    assert SpyUoW.commits == 1


async def test_update_missing_does_not_commit() -> None:
    class SpyUoW:
        commits = 0

        async def commit(self) -> None:  # pragma: no cover
            SpyUoW.commits += 1

        async def rollback(self) -> None:  # pragma: no cover
            pass

    service = TaskService(InMemoryTaskRepository(), SpyUoW())
    with pytest.raises(TaskNotFoundError):
        await service.update(999, TaskUpdate(status=TaskStatus.done))
    assert SpyUoW.commits == 0


async def test_project_service_get_missing_raises() -> None:
    service = ProjectService(InMemoryProjectRepository(), NullUnitOfWork())
    with pytest.raises(ProjectNotFoundError):
        await service.get(1)


async def test_project_service_list() -> None:
    service = ProjectService(InMemoryProjectRepository(), NullUnitOfWork())
    await service.create(ProjectCreate(name="P1"))
    page = await service.list(limit=10, offset=0)
    assert page.total == 1
    assert page.items[0].name == "P1"
