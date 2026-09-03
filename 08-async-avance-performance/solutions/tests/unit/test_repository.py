"""Tests de `SqlAlchemyTaskRepository` sur une vraie base SQLite (async, in-memory)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.db.models import ProjectRow, UserRow
from taskman.repositories import SqlAlchemyProjectRepository, SqlAlchemyTaskRepository
from taskman.schemas import (
    ChecklistItem,
    ProjectCreate,
    TaskCreate,
    TaskFilters,
    TaskStatus,
    TaskUpdate,
)


@pytest.fixture
async def owner_id(db_session: AsyncSession) -> int:
    user = UserRow(email="owner@x.co", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    return user.id


@pytest.fixture
async def project_id(db_session: AsyncSession, owner_id: int) -> int:
    row = ProjectRow(name="P", owner_id=owner_id)
    db_session.add(row)
    await db_session.flush()
    return row.id


def _new(project_id: int, **over: object) -> TaskCreate:
    base: dict[str, object] = {"title": "Tâche", "project_id": project_id}
    return TaskCreate(**{**base, **over})  # type: ignore[arg-type]


async def test_create_and_get_roundtrip(
    db_session: AsyncSession, project_id: int, owner_id: int
) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    due = datetime.now(UTC) + timedelta(days=2)
    created = await repo.create(
        _new(
            project_id, title="Écrire", due_date=due, tags=["Docs"], estimate_hours=Decimal("2.5")
        ),
        owner_id=owner_id,
    )
    assert created.id >= 1
    assert created.tags == ["docs"]
    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.created_at.tzinfo is not None
    assert fetched.due_date == due
    assert isinstance(fetched.estimate_hours, Decimal)
    assert await repo.get_owner_id(created.id) == owner_id


async def test_list_scoped_by_owner(
    db_session: AsyncSession, project_id: int, owner_id: int
) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    other = UserRow(email="other@x.co", hashed_password="x")
    db_session.add(other)
    await db_session.flush()

    await repo.create(_new(project_id, title="mine"), owner_id=owner_id)
    await repo.create(_new(project_id, title="theirs"), owner_id=other.id)

    mine, total_mine = await repo.list_page(TaskFilters(), owner_id=owner_id)
    assert total_mine == 1 and mine[0].title == "mine"

    _, total_all = await repo.list_page(TaskFilters(), owner_id=None)  # admin voit tout
    assert total_all == 2


async def test_list_filters_and_total(
    db_session: AsyncSession, project_id: int, owner_id: int
) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    await repo.create(_new(project_id, title="doc archi", priority=5), owner_id=owner_id)
    await repo.create(_new(project_id, title="autre", priority=1), owner_id=owner_id)
    await repo.create(_new(project_id, title="doc plan", priority=4), owner_id=owner_id)
    rows, total = await repo.list_page(TaskFilters(q="doc", min_priority=4), owner_id=owner_id)
    assert total == 2
    assert [t.title for t in rows] == ["doc archi", "doc plan"]


async def test_update_partial(db_session: AsyncSession, project_id: int, owner_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    created = await repo.create(_new(project_id, title="orig", priority=2), owner_id=owner_id)
    updated = await repo.update(
        created.id, TaskUpdate(status=TaskStatus.done, checklist=[ChecklistItem(label="fait")])
    )
    assert updated is not None
    assert updated.title == "orig"
    assert updated.status is TaskStatus.done
    assert [c.label for c in updated.checklist] == ["fait"]


async def test_delete(db_session: AsyncSession, project_id: int, owner_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    created = await repo.create(_new(project_id), owner_id=owner_id)
    assert await repo.delete(created.id) is True
    assert await repo.delete(created.id) is False


async def test_project_task_count_no_n_plus_1(db_session: AsyncSession, owner_id: int) -> None:
    projects = SqlAlchemyProjectRepository(db_session)
    tasks = SqlAlchemyTaskRepository(db_session)
    p1 = await projects.create(ProjectCreate(name="P1"), owner_id=owner_id)
    await projects.create(ProjectCreate(name="P2"), owner_id=owner_id)
    await tasks.create(_new(p1.id), owner_id=owner_id)
    await tasks.create(_new(p1.id), owner_id=owner_id)
    items, total = await projects.list_page(owner_id=owner_id, limit=10, offset=0)
    assert total == 2
    assert {p.name: p.task_count for p in items} == {"P1": 2, "P2": 0}
