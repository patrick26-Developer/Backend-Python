"""Implémentations SQLAlchemy des repositories (async).

Module 06 : filtrage systématique par `owner_id` (isolation multi-utilisateur).
`owner_id=None` = pas de filtre (réservé aux administrateurs, décision prise dans
le service).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.core.exceptions import EmailAlreadyRegisteredError, ProjectNotFoundError
from taskman.db.models import ProjectRow, RefreshTokenRow, TaskRow, UserRow
from taskman.schemas import (
    ChecklistItem,
    ProjectCreate,
    ProjectRead,
    SortKey,
    TaskCreate,
    TaskFilters,
    TaskRead,
    TaskStatus,
    TaskUpdate,
    UserRole,
)

_SORT_COLUMNS = {
    "priority": TaskRow.priority,
    "created_at": TaskRow.created_at,
    "due_date": TaskRow.due_date,
}


def _apply_sort(stmt: Select[tuple[TaskRow]], sort: SortKey) -> Select[tuple[TaskRow]]:
    column = _SORT_COLUMNS[sort.lstrip("-")]
    ordering = column.desc() if sort.startswith("-") else column.asc()
    return stmt.order_by(column.is_(None), ordering, TaskRow.created_at.asc())


def _task_to_read(row: TaskRow) -> TaskRead:
    return TaskRead.model_validate(row)


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TaskCreate, *, owner_id: int) -> TaskRead:
        row = TaskRow(
            owner_id=owner_id,
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
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ProjectNotFoundError(data.project_id) from exc
        await self._session.refresh(row)
        return _task_to_read(row)

    async def get(self, task_id: int) -> TaskRead | None:
        row = await self._session.get(TaskRow, task_id)
        return _task_to_read(row) if row is not None else None

    async def get_owner_id(self, task_id: int) -> int | None:
        owner_id: int | None = await self._session.scalar(
            select(TaskRow.owner_id).where(TaskRow.id == task_id)
        )
        return owner_id

    async def list(
        self, filters: TaskFilters, *, owner_id: int | None
    ) -> tuple[list[TaskRead], int]:
        stmt: Select[tuple[TaskRow]] = select(TaskRow)

        if owner_id is not None:
            stmt = stmt.where(TaskRow.owner_id == owner_id)
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

    async def mark_completed(self, task_id: int) -> TaskRead | None:
        row = await self._session.get(TaskRow, task_id)
        if row is None:
            return None
        row.status = TaskStatus.done
        row.completed_at = datetime.now(UTC)
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

    async def create(self, data: ProjectCreate, *, owner_id: int) -> ProjectRead:
        row = ProjectRow(name=data.name, owner_id=owner_id)
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

    async def get_owner_id(self, project_id: int) -> int | None:
        owner_id: int | None = await self._session.scalar(
            select(ProjectRow.owner_id).where(ProjectRow.id == project_id)
        )
        return owner_id

    async def list(
        self, *, owner_id: int | None, limit: int, offset: int
    ) -> tuple[list[ProjectRead], int]:
        count_col = func.count(TaskRow.id).label("task_count")
        stmt = (
            select(ProjectRow, count_col)
            .outerjoin(TaskRow, TaskRow.project_id == ProjectRow.id)
            .group_by(ProjectRow.id)
            .order_by(ProjectRow.id)
            .limit(limit)
            .offset(offset)
        )
        total_stmt = select(func.count()).select_from(ProjectRow)
        if owner_id is not None:
            stmt = stmt.where(ProjectRow.owner_id == owner_id)
            total_stmt = total_stmt.where(ProjectRow.owner_id == owner_id)

        total = await self._session.scalar(total_stmt)
        result = await self._session.execute(stmt)
        items = [
            ProjectRead(
                id=proj.id, name=proj.name, created_at=proj.created_at, task_count=task_count
            )
            for proj, task_count in result.all()
        ]
        return items, total or 0


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, email: str, hashed_password: str) -> UserRow:
        row = UserRow(email=email, hashed_password=hashed_password, role=UserRole.member)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise EmailAlreadyRegisteredError(email) from exc
        await self._session.refresh(row)
        return row

    async def get(self, user_id: int) -> UserRow | None:
        return await self._session.get(UserRow, user_id)

    async def get_by_email(self, email: str) -> UserRow | None:
        user: UserRow | None = await self._session.scalar(
            select(UserRow).where(UserRow.email == email)
        )
        return user

    async def list(self, *, limit: int, offset: int) -> tuple[list[UserRow], int]:
        total = await self._session.scalar(select(func.count()).select_from(UserRow))
        rows = (
            await self._session.scalars(
                select(UserRow).order_by(UserRow.id).limit(limit).offset(offset)
            )
        ).all()
        return list(rows), total or 0


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, *, jti: str, user_id: int, expires_at: datetime) -> None:
        self._session.add(
            RefreshTokenRow(jti=jti, user_id=user_id, expires_at=expires_at, revoked=False)
        )
        await self._session.flush()

    async def get(self, jti: str) -> RefreshTokenRow | None:
        return await self._session.get(RefreshTokenRow, jti)

    async def revoke(self, jti: str) -> None:
        row = await self._session.get(RefreshTokenRow, jti)
        if row is not None:
            row.revoked = True
            await self._session.flush()
