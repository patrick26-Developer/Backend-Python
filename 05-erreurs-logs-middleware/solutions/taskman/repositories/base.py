"""Contrats des couches persistance et transaction.

Module 04 : tout devient **async** (une I/O réelle, maintenant).
- `TaskRepository` / `ProjectRepository` : accès aux données.
- `UnitOfWork` : `commit` / `rollback`. `AsyncSession` le satisfait structurellement.

Le service dépend de ces *interfaces*, jamais des implémentations concrètes.
"""

from __future__ import annotations

from typing import Protocol

from taskman.schemas import (
    ProjectCreate,
    ProjectRead,
    TaskCreate,
    TaskFilters,
    TaskRead,
    TaskUpdate,
)


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class TaskRepository(Protocol):
    async def create(self, data: TaskCreate) -> TaskRead: ...

    async def get(self, task_id: int) -> TaskRead | None: ...

    async def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]: ...

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None: ...

    async def delete(self, task_id: int) -> bool: ...


class ProjectRepository(Protocol):
    async def create(self, data: ProjectCreate) -> ProjectRead: ...

    async def get(self, project_id: int) -> ProjectRead | None: ...

    async def list(self, *, limit: int, offset: int) -> tuple[list[ProjectRead], int]: ...
