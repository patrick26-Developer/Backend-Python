"""Couche métier des tâches.

Module 06 : le service est **conscient de l'acteur** (`actor: UserRead`). Un membre
ne voit et ne modifie que **ses** tâches ; un `admin` voit tout.

Choix de sécurité : accéder à la tâche d'un autre renvoie **404** (et non 403) —
on ne révèle pas l'existence d'une ressource qu'on n'a pas le droit de voir (OWASP,
défense contre l'énumération).
"""

from __future__ import annotations

from taskman.core.exceptions import TaskNotFoundError
from taskman.repositories import TaskRepository, UnitOfWork
from taskman.schemas import (
    TaskCreate,
    TaskFilters,
    TaskPage,
    TaskRead,
    TaskUpdate,
    UserRead,
    UserRole,
)


class TaskService:
    def __init__(self, tasks: TaskRepository, uow: UnitOfWork, actor: UserRead) -> None:
        self._tasks = tasks
        self._uow = uow
        self._actor = actor

    @property
    def _scope(self) -> int | None:
        """`None` pour un admin (voit tout), l'id de l'acteur sinon."""
        return None if self._actor.role is UserRole.admin else self._actor.id

    async def _assert_can_access(self, task_id: int) -> None:
        owner_id = await self._tasks.get_owner_id(task_id)
        if owner_id is None or (self._scope is not None and owner_id != self._scope):
            raise TaskNotFoundError(task_id)

    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._tasks.create(data, owner_id=self._actor.id)
        await self._uow.commit()
        return task

    async def get(self, task_id: int) -> TaskRead:
        await self._assert_can_access(task_id)
        task = await self._tasks.get(task_id)
        assert task is not None  # garanti par _assert_can_access
        return task

    async def list(self, filters: TaskFilters) -> TaskPage:
        items, total = await self._tasks.list(filters, owner_id=self._scope)
        return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead:
        await self._assert_can_access(task_id)
        task = await self._tasks.update(task_id, changes)
        assert task is not None
        await self._uow.commit()
        return task

    async def delete(self, task_id: int) -> None:
        await self._assert_can_access(task_id)
        await self._tasks.delete(task_id)
        await self._uow.commit()
