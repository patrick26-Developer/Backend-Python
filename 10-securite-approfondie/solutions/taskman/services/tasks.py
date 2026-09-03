"""Couche métier des tâches.

Module 08 : le service porte le **cache** (agrégats de projet) et son
**invalidation**, la pagination *cursor*, et l'export streamé.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from datetime import datetime

from taskman.core.cache import Cache
from taskman.core.exceptions import BadRequestError, TaskNotFoundError
from taskman.repositories import TaskRepository, UnitOfWork
from taskman.schemas import (
    TaskCreate,
    TaskFilters,
    TaskPage,
    TaskRead,
    TaskStats,
    TaskStatus,
    TaskUpdate,
    UserRead,
    UserRole,
)

_STATS_TTL = 60  # secondes


def _encode_cursor(created_at: datetime, task_id: int) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": task_id}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(token: str) -> tuple[datetime, int]:
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()))
        return datetime.fromisoformat(data["c"]), int(data["i"])
    except (ValueError, KeyError, TypeError) as exc:
        raise BadRequestError("cursor invalide") from exc


class TaskService:
    def __init__(
        self,
        tasks: TaskRepository,
        uow: UnitOfWork,
        actor: UserRead,
        cache: Cache,
    ) -> None:
        self._tasks = tasks
        self._uow = uow
        self._actor = actor
        self._cache = cache

    @property
    def _scope(self) -> int | None:
        return None if self._actor.role is UserRole.admin else self._actor.id

    async def _assert_can_access(self, task_id: int) -> None:
        owner_id = await self._tasks.get_owner_id(task_id)
        if owner_id is None or (self._scope is not None and owner_id != self._scope):
            raise TaskNotFoundError(task_id)

    async def _invalidate_project(self, project_id: int) -> None:
        await self._cache.delete(f"project:{project_id}:stats")

    # --- écritures -------------------------------------------------
    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._tasks.create(data, owner_id=self._actor.id)
        await self._uow.commit()
        await self._invalidate_project(task.project_id)
        return task

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead:
        await self._assert_can_access(task_id)
        task = await self._tasks.update(task_id, changes)
        assert task is not None
        await self._uow.commit()
        await self._invalidate_project(task.project_id)
        return task

    async def complete(self, task_id: int) -> TaskRead:
        await self._assert_can_access(task_id)
        task = await self._tasks.mark_completed(task_id)
        assert task is not None
        await self._uow.commit()
        await self._invalidate_project(task.project_id)
        return task

    async def delete(self, task_id: int) -> None:
        await self._assert_can_access(task_id)
        task = await self._tasks.get(task_id)
        await self._tasks.delete(task_id)
        await self._uow.commit()
        if task is not None:
            await self._invalidate_project(task.project_id)

    # --- lectures -------------------------------------------------
    async def get(self, task_id: int) -> TaskRead:
        await self._assert_can_access(task_id)
        task = await self._tasks.get(task_id)
        assert task is not None
        return task

    def _use_keyset(self, filters: TaskFilters) -> bool:
        return filters.cursor is not None or (filters.offset == 0 and filters.sort == "-created_at")

    async def list(self, filters: TaskFilters) -> TaskPage:
        if not self._use_keyset(filters):
            items, total = await self._tasks.list_page(filters, owner_id=self._scope)
            return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)

        after = _decode_cursor(filters.cursor) if filters.cursor is not None else None
        rows = await self._tasks.list_keyset(owner_id=self._scope, limit=filters.limit, after=after)
        next_cursor: str | None = None
        if len(rows) == filters.limit:
            last = rows[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)
        return TaskPage(
            items=rows,
            total=len(rows),
            limit=filters.limit,
            offset=filters.offset,
            next_cursor=next_cursor,
        )

    async def export(self) -> AsyncIterator[TaskRead]:
        """Générateur pour l'export NDJSON — mémoire constante."""
        async for task in self._tasks.iter_by_owner(self._scope):
            yield task

    async def stats(self, project_id: int) -> TaskStats:
        key = f"project:{project_id}:stats"
        if (cached := await self._cache.get(key)) is not None:
            return TaskStats.model_validate_json(cached)

        by_status, overdue = await self._tasks.project_stats(project_id)
        total = sum(by_status.values())
        done = by_status.get(TaskStatus.done.value, 0)
        stats = TaskStats(
            project_id=project_id,
            total=total,
            by_status=by_status,
            overdue=overdue,
            completion_rate=round(done / total, 3) if total else 0.0,
        )
        await self._cache.set(key, stats.model_dump_json(), ttl=_STATS_TTL)
        return stats
