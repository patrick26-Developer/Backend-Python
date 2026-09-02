"""Implémentations **en mémoire** des repositories.

Rôle depuis le Module 04 : support des tests de la couche **service** (rapides,
sans base). Les vrais tests de persistance utilisent `SqlAlchemyTaskRepository`
sur SQLite (voir tests/).

Les méthodes sont `async` pour respecter le `Protocol` — même si elles ne font
aucune I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from operator import attrgetter

from taskman.schemas import (
    ProjectCreate,
    ProjectRead,
    SortKey,
    TaskCreate,
    TaskFilters,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _sorted(rows: list[TaskRead], sort: SortKey) -> list[TaskRead]:
    reverse = sort.startswith("-")
    field = sort.lstrip("-")
    rows.sort(key=attrgetter("created_at"))
    if field == "due_date":
        rows.sort(
            key=lambda t: (t.due_date is None, t.due_date or datetime.min.replace(tzinfo=UTC)),
            reverse=reverse,
        )
    else:
        rows.sort(key=attrgetter(field), reverse=reverse)
    return rows


class NullUnitOfWork:
    """`UnitOfWork` sans effet : rien à valider quand tout est en mémoire."""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._items: dict[int, TaskRead] = {}
        self._seq = 0

    def clear(self) -> None:
        self._items.clear()
        self._seq = 0

    async def create(self, data: TaskCreate) -> TaskRead:
        self._seq += 1
        now = _now()
        task = TaskRead(
            id=self._seq,
            status=TaskStatus.todo,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self._items[task.id] = task
        return task

    async def get(self, task_id: int) -> TaskRead | None:
        return self._items.get(task_id)

    async def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]:
        rows = list(self._items.values())
        if filters.status is not None:
            rows = [t for t in rows if t.status == filters.status]
        if filters.min_priority is not None:
            rows = [t for t in rows if t.priority >= filters.min_priority]
        if filters.project_id is not None:
            rows = [t for t in rows if t.project_id == filters.project_id]
        if filters.q:
            needle = filters.q.casefold()
            rows = [
                t
                for t in rows
                if needle in t.title.casefold()
                or (t.description is not None and needle in t.description.casefold())
            ]
        total = len(rows)
        rows = _sorted(rows, filters.sort)
        return rows[filters.offset : filters.offset + filters.limit], total

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        current = self._items.get(task_id)
        if current is None:
            return None
        patch = changes.model_dump(exclude_unset=True)
        if not patch:
            return current
        data = current.model_dump()
        data.update(patch)
        data["updated_at"] = _now()
        updated = TaskRead.model_validate(data)
        self._items[task_id] = updated
        return updated

    async def delete(self, task_id: int) -> bool:
        return self._items.pop(task_id, None) is not None


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._items: dict[int, ProjectRead] = {}
        self._seq = 0

    def clear(self) -> None:
        self._items.clear()
        self._seq = 0

    async def create(self, data: ProjectCreate) -> ProjectRead:
        self._seq += 1
        project = ProjectRead(id=self._seq, name=data.name, created_at=_now(), task_count=0)
        self._items[project.id] = project
        return project

    async def get(self, project_id: int) -> ProjectRead | None:
        return self._items.get(project_id)

    async def list(self, *, limit: int, offset: int) -> tuple[list[ProjectRead], int]:
        rows = sorted(self._items.values(), key=attrgetter("id"))
        return rows[offset : offset + limit], len(rows)
