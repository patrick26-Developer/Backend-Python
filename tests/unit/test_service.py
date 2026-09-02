"""Tests unitaires de la couche service — sans HTTP, sans base de données.

On utilise les repositories **en mémoire** + `NullUnitOfWork` : le service se teste
en isolation totale grâce aux `Protocol`.
"""

from __future__ import annotations

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
    assert page.limit == 1
    assert len(page.items) == 1


async def test_get_missing_returns_none() -> None:
    service, _ = _task_service()
    assert await service.get(42) is None


async def test_update_missing_returns_none() -> None:
    service, _ = _task_service()
    assert await service.update(42, TaskUpdate(status=TaskStatus.done)) is None


async def test_delete_reports_boolean() -> None:
    service, _ = _task_service()
    created = await service.create(TaskCreate(title="x", project_id=1))
    assert await service.delete(created.id) is True
    assert await service.delete(created.id) is False


async def test_commit_called_on_write() -> None:
    class SpyUoW:
        commits = 0

        async def commit(self) -> None:
            SpyUoW.commits += 1

        async def rollback(self) -> None:  # pragma: no cover
            pass

    service = TaskService(InMemoryTaskRepository(), SpyUoW())
    await service.create(TaskCreate(title="x", project_id=1))
    await service.list(TaskFilters())  # lecture -> pas de commit
    assert SpyUoW.commits == 1


async def test_project_service_wraps_page() -> None:
    service = ProjectService(InMemoryProjectRepository(), NullUnitOfWork())
    await service.create(ProjectCreate(name="P1"))
    page = await service.list(limit=10, offset=0)
    assert page.total == 1
    assert page.items[0].name == "P1"
