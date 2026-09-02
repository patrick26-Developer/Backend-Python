"""Persistance en mémoire (échafaudage — remplacé par SQLAlchemy au Module 04).

Le store parle en `TaskRead` (le modèle riche) et ne connaît rien de HTTP.
`is_overdue` est un `computed_field` : recalculé à chaque lecture, jamais stocké.
"""

from __future__ import annotations

from datetime import UTC, datetime
from operator import attrgetter

from .models import (
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
    # clé secondaire déterministe
    rows.sort(key=attrgetter("created_at"))
    if field == "due_date":
        # les tâches sans échéance en dernier, quel que soit le sens
        rows.sort(
            key=lambda t: (t.due_date is None, t.due_date or datetime.min.replace(tzinfo=UTC)),
            reverse=reverse,
        )
    else:
        rows.sort(key=attrgetter(field), reverse=reverse)
    return rows


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._items: dict[int, TaskRead] = {}
        self._seq: int = 0

    def clear(self) -> None:
        self._items.clear()
        self._seq = 0

    def create(self, data: TaskCreate) -> TaskRead:
        self._seq += 1
        now = _now()
        return self._put(
            TaskRead(
                id=self._seq,
                status=TaskStatus.todo,
                created_at=now,
                updated_at=now,
                **data.model_dump(),
            )
        )

    def get(self, task_id: int) -> TaskRead | None:
        return self._items.get(task_id)

    def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]:
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

    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        current = self._items.get(task_id)
        if current is None:
            return None

        patch = changes.model_dump(exclude_unset=True)
        if not patch:
            return current

        data = current.model_dump()
        data.update(patch)
        data["updated_at"] = _now()
        # model_validate revalide TOUT (y compris la checklist imbriquée) ;
        # `is_overdue` (computed) présent dans `data` est ignoré puis recalculé.
        return self._put(TaskRead.model_validate(data))

    def delete(self, task_id: int) -> bool:
        return self._items.pop(task_id, None) is not None

    def _put(self, task: TaskRead) -> TaskRead:
        self._items[task.id] = task
        return task
