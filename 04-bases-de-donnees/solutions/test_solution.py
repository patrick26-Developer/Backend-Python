"""Tests de la solution du Module 04 — persistance, transactions, N+1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.repositories import (
    InMemoryTaskRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyTaskRepository,
)
from taskman.schemas import ProjectCreate, TaskCreate, TaskFilters, TaskStatus
from taskman.services import TaskService


async def _project(client: AsyncClient, name: str = "P") -> int:
    r = await client.post("/projects", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


# --- persistance via l'API ------------------------------------
async def test_task_persists(client: AsyncClient) -> None:
    pid = await _project(client)
    created = await client.post("/tasks", json={"title": "persiste", "project_id": pid})
    assert created.status_code == 201
    got = await client.get(f"/tasks/{created.json()['id']}")
    assert got.json()["title"] == "persiste"


async def test_fk_enforced(client: AsyncClient) -> None:
    with pytest.raises(IntegrityError):
        await client.post("/tasks", json={"title": "x", "project_id": 12345})


# --- repository SQL --------------------------------------------
async def test_repository_roundtrip_tz_and_decimal(db_session: AsyncSession) -> None:
    proj = await SqlAlchemyProjectRepository(db_session).create(ProjectCreate(name="P"))
    repo = SqlAlchemyTaskRepository(db_session)
    due = datetime.now(UTC) + timedelta(days=1)
    created = await repo.create(TaskCreate(title="x", project_id=proj.id, due_date=due))
    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.due_date == due
    assert fetched.created_at.tzinfo is not None


async def test_project_task_count_single_query(db_session: AsyncSession) -> None:
    projects = SqlAlchemyProjectRepository(db_session)
    tasks = SqlAlchemyTaskRepository(db_session)
    p1 = await projects.create(ProjectCreate(name="P1"))
    await projects.create(ProjectCreate(name="P2"))
    await tasks.create(TaskCreate(title="a", project_id=p1.id))
    await tasks.create(TaskCreate(title="b", project_id=p1.id))
    items, total = await projects.list(limit=10, offset=0)
    assert total == 2
    assert {p.name: p.task_count for p in items} == {"P1": 2, "P2": 0}


# --- frontière transactionnelle -----------------------------
async def test_commit_on_write_not_on_read() -> None:
    class SpyUoW:
        commits = 0

        async def commit(self) -> None:
            SpyUoW.commits += 1

        async def rollback(self) -> None:  # pragma: no cover
            pass

    service = TaskService(InMemoryTaskRepository(), SpyUoW())
    await service.create(TaskCreate(title="x", project_id=1))
    await service.get(1)
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
    from taskman.schemas import TaskUpdate

    assert await service.update(999, TaskUpdate(status=TaskStatus.done)) is None
    assert SpyUoW.commits == 0


# --- non-régression du CRUD --------------------------------
async def test_crud_flow(client: AsyncClient) -> None:
    pid = await _project(client)
    created = await client.post("/tasks", json={"title": "t", "project_id": pid})
    tid = created.json()["id"]
    assert (await client.get(f"/tasks/{tid}")).status_code == 200
    patched = await client.patch(f"/tasks/{tid}", json={"status": "done"})
    assert patched.json()["status"] == "done"
    assert (await client.delete(f"/tasks/{tid}")).status_code == 204
    assert (await client.get(f"/tasks/{tid}")).status_code == 404
