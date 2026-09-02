"""Couche métier des tâches (async depuis le Module 04).

Le service est la **frontière transactionnelle** : il décide quand `commit`.
- lectures (`get`, `list`) : aucun commit ;
- écritures (`create`, `update`, `delete`) : `commit` **après** l'opération du
  repository, seulement si elle a réussi.

En cas d'exception, la session est fermée sans commit par la dépendance
`get_session` (`async with`) → les changements sont abandonnés (rollback implicite).

Toujours : ni `import fastapi`, ni SQL ici.
"""

from __future__ import annotations

from taskman.repositories import TaskRepository, UnitOfWork
from taskman.schemas import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate


class TaskService:
    def __init__(self, tasks: TaskRepository, uow: UnitOfWork) -> None:
        self._tasks = tasks
        self._uow = uow

    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._tasks.create(data)
        await self._uow.commit()
        return task

    async def get(self, task_id: int) -> TaskRead | None:
        return await self._tasks.get(task_id)

    async def list(self, filters: TaskFilters) -> TaskPage:
        items, total = await self._tasks.list(filters)
        return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        task = await self._tasks.update(task_id, changes)
        if task is not None:
            await self._uow.commit()
        return task

    async def delete(self, task_id: int) -> bool:
        deleted = await self._tasks.delete(task_id)
        if deleted:
            await self._uow.commit()
        return deleted
