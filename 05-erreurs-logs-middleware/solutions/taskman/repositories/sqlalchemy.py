"""Implémentations SQLAlchemy des repositories (async).

Grâce au `Protocol` du Module 03, brancher ces classes ne demande **aucun**
changement au service ni aux routes — seule l'injection (`api/deps.py`) change.

Chaque repository reçoit une `AsyncSession` (fournie par `get_session`). Il n'ouvre
ni ne ferme la session, ne commit pas : c'est le service qui décide (`UnitOfWork`).
Il utilise `flush()` pour obtenir les identifiants générés sans valider.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.core.exceptions import ProjectNotFoundError
from taskman.db.models import ProjectRow, TaskRow
from taskman.schemas import (
    ChecklistItem,
    ProjectCreate,
    ProjectRead,
    SortKey,
    TaskCreate,
    TaskFilters,
    TaskRead,
    TaskUpdate,
)

_SORT_COLUMNS = {
    "priority": TaskRow.priority,
    "created_at": TaskRow.created_at,
    "due_date": TaskRow.due_date,
}


def _apply_sort(stmt: Select[tuple[TaskRow]], sort: SortKey) -> Select[tuple[TaskRow]]:
    column = _SORT_COLUMNS[sort.lstrip("-")]
    ordering = column.desc() if sort.startswith("-") else column.asc()
    # échéances nulles toujours en dernier, quel que soit le sens
    return stmt.order_by(column.is_(None), ordering, TaskRow.created_at.asc())


def _task_to_read(row: TaskRow) -> TaskRead:
    return TaskRead.model_validate(row)


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TaskCreate) -> TaskRead:
        row = TaskRow(
            project_id=data.project_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            due_date=data.due_date,
            tags=list(data.tags),
            assignee_email=data.assignee_email,
            estimate_hours=data.estimate_hours,
            checklist=[item.model_dump() for item in data.checklist],
        )
        self._session.add(row)
        try:
            await self._session.flush()  # attribue l'id, sans committer
        except IntegrityError as exc:
            # La seule contrainte pouvant échouer ici : la FK vers `projects`.
            # On traduit l'erreur d'infrastructure en erreur MÉTIER.
            await self._session.rollback()
            raise ProjectNotFoundError(data.project_id) from exc
        await self._session.refresh(row)
        return _task_to_read(row)

    async def get(self, task_id: int) -> TaskRead | None:
        row = await self._session.get(TaskRow, task_id)
        return _task_to_read(row) if row is not None else None

    async def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]:
        stmt: Select[tuple[TaskRow]] = select(TaskRow)

        if filters.status is not None:
            stmt = stmt.where(TaskRow.status == filters.status)
        if filters.min_priority is not None:
            stmt = stmt.where(TaskRow.priority >= filters.min_priority)
        if filters.project_id is not None:
            stmt = stmt.where(TaskRow.project_id == filters.project_id)
        if filters.q:
            like = f"%{filters.q}%"
            stmt = stmt.where(or_(TaskRow.title.ilike(like), TaskRow.description.ilike(like)))

        total = await self._session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )

        stmt = _apply_sort(stmt, filters.sort).limit(filters.limit).offset(filters.offset)
        rows: Sequence[TaskRow] = (await self._session.scalars(stmt)).all()
        return [_task_to_read(r) for r in rows], total or 0

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        row = await self._session.get(TaskRow, task_id)
        if row is None:
            return None

        patch: dict[str, Any] = changes.model_dump(exclude_unset=True)
        for key, value in patch.items():
            if key == "checklist" and value is not None:
                value = [
                    v if isinstance(v, dict) else ChecklistItem.model_validate(v).model_dump()
                    for v in value
                ]
            setattr(row, key, value)

        await self._session.flush()
        await self._session.refresh(row)
        return _task_to_read(row)

    async def delete(self, task_id: int) -> bool:
        row = await self._session.get(TaskRow, task_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ProjectCreate) -> ProjectRead:
        row = ProjectRow(name=data.name)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return ProjectRead(id=row.id, name=row.name, created_at=row.created_at, task_count=0)

    async def get(self, project_id: int) -> ProjectRead | None:
        row = await self._session.get(ProjectRow, project_id)
        if row is None:
            return None
        count = await self._session.scalar(
            select(func.count()).select_from(TaskRow).where(TaskRow.project_id == project_id)
        )
        return ProjectRead(
            id=row.id, name=row.name, created_at=row.created_at, task_count=count or 0
        )

    async def list(self, *, limit: int, offset: int) -> tuple[list[ProjectRead], int]:
        # Compte des tâches en UNE requête (LEFT JOIN + GROUP BY) — PAS de N+1.
        count_col = func.count(TaskRow.id).label("task_count")
        stmt = (
            select(ProjectRow, count_col)
            .outerjoin(TaskRow, TaskRow.project_id == ProjectRow.id)
            .group_by(ProjectRow.id)
            .order_by(ProjectRow.id)
            .limit(limit)
            .offset(offset)
        )
        total = await self._session.scalar(select(func.count()).select_from(ProjectRow))
        result = await self._session.execute(stmt)
        items = [
            ProjectRead(
                id=proj.id, name=proj.name, created_at=proj.created_at, task_count=task_count
            )
            for proj, task_count in result.all()
        ]
        return items, total or 0
