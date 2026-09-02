"""Tests de `SqlAlchemyTaskRepository` sur une vraie base SQLite (async, in-memory)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.db.models import ProjectRow
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
async def project_id(db_session: AsyncSession) -> int:
    row = ProjectRow(name="P")
    db_session.add(row)
    await db_session.flush()
    return row.id


def _new(project_id: int, **over: object) -> TaskCreate:
    base: dict[str, object] = {"title": "Tâche", "project_id": project_id}
    return TaskCreate(**{**base, **over})  # type: ignore[arg-type]


async def test_create_and_get_roundtrip(db_session: AsyncSession, project_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    due = datetime.now(UTC) + timedelta(days=2)
    created = await repo.create(
        _new(project_id, title="Écrire", due_date=due, tags=["Docs"], estimate_hours=Decimal("2.5"))
    )
    assert created.id >= 1
    assert created.tags == ["docs"]  # normalisé par le schéma
    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.created_at.tzinfo is not None  # TZDateTime -> aware
    assert fetched.due_date == due
    assert isinstance(fetched.estimate_hours, Decimal)


async def test_get_missing_returns_none(db_session: AsyncSession) -> None:
    assert await SqlAlchemyTaskRepository(db_session).get(999) is None


async def test_list_filters_and_total(db_session: AsyncSession, project_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    await repo.create(_new(project_id, title="doc archi", priority=5))
    await repo.create(_new(project_id, title="autre", priority=1))
    await repo.create(_new(project_id, title="doc plan", priority=4))

    rows, total = await repo.list(TaskFilters(q="doc", min_priority=4))
    assert total == 2
    assert [t.title for t in rows] == ["doc archi", "doc plan"]  # tri -priority


async def test_list_pagination(db_session: AsyncSession, project_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    for i in range(5):
        await repo.create(_new(project_id, title=f"t{i}", priority=i + 1))
    rows, total = await repo.list(TaskFilters(limit=2, offset=1, sort="-priority"))
    assert total == 5
    assert [t.title for t in rows] == ["t3", "t2"]


async def test_update_partial(db_session: AsyncSession, project_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    created = await repo.create(_new(project_id, title="orig", priority=2))
    updated = await repo.update(
        created.id, TaskUpdate(status=TaskStatus.done, checklist=[ChecklistItem(label="fait")])
    )
    assert updated is not None
    assert updated.title == "orig"
    assert updated.status is TaskStatus.done
    assert [c.label for c in updated.checklist] == ["fait"]
    assert updated.updated_at >= created.updated_at


async def test_update_null_clears_description(db_session: AsyncSession, project_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    created = await repo.create(_new(project_id, description="à effacer"))
    updated = await repo.update(created.id, TaskUpdate(description=None))
    assert updated is not None and updated.description is None


async def test_delete(db_session: AsyncSession, project_id: int) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    created = await repo.create(_new(project_id))
    assert await repo.delete(created.id) is True
    assert await repo.delete(created.id) is False


async def test_project_list_task_count_no_n_plus_1(db_session: AsyncSession) -> None:
    projects = SqlAlchemyProjectRepository(db_session)
    tasks = SqlAlchemyTaskRepository(db_session)
    p1 = await projects.create(ProjectCreate(name="P1"))
    await projects.create(ProjectCreate(name="P2"))
    await tasks.create(_new(p1.id))
    await tasks.create(_new(p1.id))

    items, total = await projects.list(limit=10, offset=0)
    assert total == 2
    by_name = {p.name: p.task_count for p in items}
    assert by_name == {"P1": 2, "P2": 0}
