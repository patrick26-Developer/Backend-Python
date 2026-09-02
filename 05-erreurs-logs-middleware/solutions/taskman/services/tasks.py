"""Couche métier des tâches.

Module 05 : le service lève des **exceptions métier** (`TaskNotFoundError`) au lieu
de renvoyer `None`. Les routes n'ont plus à décider du code HTTP — un handler
central s'en charge.

Toujours : ni `import fastapi`, ni SQL, ni HTTP ici.
"""

from __future__ import annotations

from taskman.core.exceptions import TaskNotFoundError
from taskman.repositories import TaskRepository, UnitOfWork
from taskman.schemas import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate


class TaskService:
    def __init__(self, tasks: TaskRepository, uow: UnitOfWork) -> None:
        self._tasks = tasks
        self._uow = uow

    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._tasks.create(data)  # lève ProjectNotFoundError si FK invalide
        await self._uow.commit()
        return task

    async def get(self, task_id: int) -> TaskRead:
        task = await self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def list(self, filters: TaskFilters) -> TaskPage:
        items, total = await self._tasks.list(filters)
        return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead:
        task = await self._tasks.update(task_id, changes)
        if task is None:
            raise TaskNotFoundError(task_id)
        await self._uow.commit()
        return task

    async def delete(self, task_id: int) -> None:
        if not await self._tasks.delete(task_id):
            raise TaskNotFoundError(task_id)
        await self._uow.commit()
