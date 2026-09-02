"""Tests unitaires des services métier — sans HTTP, sans base.

Repositories **en mémoire** + `NullUnitOfWork`. Depuis le Module 06, les services
reçoivent un `actor: UserRead`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from taskman.core.exceptions import ProjectNotFoundError, TaskNotFoundError
from taskman.repositories import (
    InMemoryProjectRepository,
    InMemoryTaskRepository,
    NullUnitOfWork,
)
from taskman.schemas import (
    ProjectCreate,
    TaskCreate,
    TaskFilters,
    TaskStatus,
    TaskUpdate,
    UserRead,
    UserRole,
)
from taskman.services import ProjectService, TaskService


def _user(*, uid: int = 1, role: UserRole = UserRole.member) -> UserRead:
    return UserRead(
        id=uid, email=f"u{uid}@x.co", role=role, is_active=True, created_at=datetime.now(UTC)
    )


def _svc(actor: UserRead | None = None) -> tuple[TaskService, InMemoryTaskRepository]:
    repo = InMemoryTaskRepository()
    return TaskService(repo, NullUnitOfWork(), actor or _user()), repo


async def test_create_then_list_scoped_to_owner() -> None:
    repo = InMemoryTaskRepository()
    alice = TaskService(repo, NullUnitOfWork(), _user(uid=1))
    bob = TaskService(repo, NullUnitOfWork(), _user(uid=2))

    await alice.create(TaskCreate(title="a", project_id=1))
    await bob.create(TaskCreate(title="b", project_id=1))

    assert (await alice.list(TaskFilters())).total == 1
    assert (await bob.list(TaskFilters())).total == 1


async def test_admin_sees_all() -> None:
    repo = InMemoryTaskRepository()
    member = TaskService(repo, NullUnitOfWork(), _user(uid=1))
    admin = TaskService(repo, NullUnitOfWork(), _user(uid=9, role=UserRole.admin))
    await member.create(TaskCreate(title="a", project_id=1))
    assert (await admin.list(TaskFilters())).total == 1


async def test_get_others_task_is_not_found() -> None:
    repo = InMemoryTaskRepository()
    alice = TaskService(repo, NullUnitOfWork(), _user(uid=1))
    bob = TaskService(repo, NullUnitOfWork(), _user(uid=2))
    task = await alice.create(TaskCreate(title="x", project_id=1))
    with pytest.raises(TaskNotFoundError):
        await bob.get(task.id)


async def test_get_missing_raises() -> None:
    service, _ = _svc()
    with pytest.raises(TaskNotFoundError):
        await service.get(42)


async def test_update_missing_raises() -> None:
    service, _ = _svc()
    with pytest.raises(TaskNotFoundError):
        await service.update(42, TaskUpdate(status=TaskStatus.done))


async def test_delete_missing_raises() -> None:
    service, _ = _svc()
    with pytest.raises(TaskNotFoundError):
        await service.delete(42)


async def test_commit_called_on_write_not_read() -> None:
    class SpyUoW:
        commits = 0

        async def commit(self) -> None:
            SpyUoW.commits += 1

        async def rollback(self) -> None:  # pragma: no cover
            pass

    service = TaskService(InMemoryTaskRepository(), SpyUoW(), _user())
    await service.create(TaskCreate(title="x", project_id=1))
    await service.list(TaskFilters())
    assert SpyUoW.commits == 1


async def test_project_service_isolation() -> None:
    repo = InMemoryProjectRepository()
    alice = ProjectService(repo, NullUnitOfWork(), _user(uid=1))
    bob = ProjectService(repo, NullUnitOfWork(), _user(uid=2))
    p = await alice.create(ProjectCreate(name="P1"))
    with pytest.raises(ProjectNotFoundError):
        await bob.get(p.id)
    assert (await bob.list(limit=10, offset=0)).total == 0
