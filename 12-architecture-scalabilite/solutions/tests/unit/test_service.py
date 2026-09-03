"""Tests unitaires des services métier — sans HTTP, sans base.

Repositories **en mémoire** + `NullUnitOfWork` + `InMemoryCache`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from taskman.core.cache import InMemoryCache
from taskman.core.exceptions import ProjectNotFoundError, TaskNotFoundError
from taskman.outbox import InMemoryOutboxRepository
from taskman.realtime import InMemoryEventPublisher
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


def _task_svc(
    repo: InMemoryTaskRepository, actor: UserRead, uow: object | None = None
) -> TaskService:
    return TaskService(
        repo,
        uow or NullUnitOfWork(),  # type: ignore[arg-type]
        actor,
        InMemoryCache(),
        InMemoryOutboxRepository(),
        InMemoryEventPublisher(),
    )


def _svc(actor: UserRead | None = None) -> tuple[TaskService, InMemoryTaskRepository]:
    repo = InMemoryTaskRepository()
    return _task_svc(repo, actor or _user()), repo


# --- isolation (Module 06) ---------------------------------
async def test_list_scoped_to_owner() -> None:
    repo = InMemoryTaskRepository()
    alice, bob = _task_svc(repo, _user(uid=1)), _task_svc(repo, _user(uid=2))
    await alice.create(TaskCreate(title="a", project_id=1))
    await bob.create(TaskCreate(title="b", project_id=1))
    assert (await alice.list(TaskFilters())).total == 1
    assert (await bob.list(TaskFilters())).total == 1


async def test_admin_sees_all() -> None:
    repo = InMemoryTaskRepository()
    member = _task_svc(repo, _user(uid=1))
    admin = _task_svc(repo, _user(uid=9, role=UserRole.admin))
    await member.create(TaskCreate(title="a", project_id=1))
    assert (await admin.list(TaskFilters())).total == 1


async def test_get_others_task_is_not_found() -> None:
    repo = InMemoryTaskRepository()
    alice, bob = _task_svc(repo, _user(uid=1)), _task_svc(repo, _user(uid=2))
    task = await alice.create(TaskCreate(title="x", project_id=1))
    with pytest.raises(TaskNotFoundError):
        await bob.get(task.id)


async def test_missing_raises() -> None:
    service, _ = _svc()
    with pytest.raises(TaskNotFoundError):
        await service.get(42)
    with pytest.raises(TaskNotFoundError):
        await service.update(42, TaskUpdate(status=TaskStatus.done))
    with pytest.raises(TaskNotFoundError):
        await service.delete(42)


async def test_commit_on_write_not_read() -> None:
    class SpyUoW:
        commits = 0

        async def commit(self) -> None:
            SpyUoW.commits += 1

        async def rollback(self) -> None:  # pragma: no cover
            pass

    service = TaskService(
        InMemoryTaskRepository(),
        SpyUoW(),
        _user(),
        InMemoryCache(),
        InMemoryOutboxRepository(),
        InMemoryEventPublisher(),
    )
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


# --- Module 08 : cache & invalidation ---------------------
async def test_stats_are_cached_then_invalidated() -> None:
    repo = InMemoryTaskRepository()
    cache = InMemoryCache()
    svc = TaskService(
        repo, NullUnitOfWork(), _user(), cache, InMemoryOutboxRepository(), InMemoryEventPublisher()
    )
    await svc.create(TaskCreate(title="a", project_id=7))

    s1 = await svc.stats(7)
    assert s1.total == 1
    assert await cache.get("project:7:stats") is not None  # mis en cache

    # une nouvelle tâche invalide le cache du projet
    await svc.create(TaskCreate(title="b", project_id=7))
    assert await cache.get("project:7:stats") is None
    s2 = await svc.stats(7)
    assert s2.total == 2


async def test_stats_completion_rate() -> None:
    repo = InMemoryTaskRepository()
    svc = TaskService(
        repo,
        NullUnitOfWork(),
        _user(),
        InMemoryCache(),
        InMemoryOutboxRepository(),
        InMemoryEventPublisher(),
    )
    t1 = await svc.create(TaskCreate(title="a", project_id=1))
    await svc.create(TaskCreate(title="b", project_id=1))
    await svc.complete(t1.id)
    stats = await svc.stats(1)
    assert stats.by_status["done"] == 1
    assert stats.completion_rate == 0.5


# --- Module 08 : pagination cursor -----------------------
async def test_cursor_pagination_walks_all_without_overlap() -> None:
    repo = InMemoryTaskRepository()
    svc = TaskService(
        repo,
        NullUnitOfWork(),
        _user(),
        InMemoryCache(),
        InMemoryOutboxRepository(),
        InMemoryEventPublisher(),
    )
    for i in range(5):
        await svc.create(TaskCreate(title=f"t{i}", project_id=1))

    seen: list[int] = []
    cursor: str | None = None
    for _ in range(10):  # garde-fou anti-boucle infinie
        page = await svc.list(TaskFilters(limit=2, sort="-created_at", cursor=cursor))
        seen.extend(t.id for t in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert sorted(seen) == [1, 2, 3, 4, 5]
    assert len(seen) == len(set(seen))  # aucun doublon


# --- Module 08 : export ----------------------------------
async def test_export_yields_all_owner_tasks() -> None:
    repo = InMemoryTaskRepository()
    alice = TaskService(
        repo,
        NullUnitOfWork(),
        _user(uid=1),
        InMemoryCache(),
        InMemoryOutboxRepository(),
        InMemoryEventPublisher(),
    )
    bob = TaskService(
        repo,
        NullUnitOfWork(),
        _user(uid=2),
        InMemoryCache(),
        InMemoryOutboxRepository(),
        InMemoryEventPublisher(),
    )
    await alice.create(TaskCreate(title="a1", project_id=1))
    await alice.create(TaskCreate(title="a2", project_id=1))
    await bob.create(TaskCreate(title="b1", project_id=1))

    titles = [t.title async for t in alice.export()]
    assert sorted(titles) == ["a1", "a2"]
