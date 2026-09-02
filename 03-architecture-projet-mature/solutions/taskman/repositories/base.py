"""Contrat de la couche persistance.

`TaskRepository` est un `Protocol` : n'importe quelle classe qui expose ces
méthodes *est* un `TaskRepository`, sans héritage explicite (typage structurel).

- Module 03 : une seule implémentation, `InMemoryTaskRepository`.
- Module 04 : `SqlAlchemyTaskRepository` — les routes et le service ne changent pas.

Les méthodes sont **synchrones** ici : aucune I/O réelle. Le Module 04 introduit
la version `async` (et explique le coût de cette migration).
"""

from __future__ import annotations

from typing import Protocol

from taskman.schemas import TaskCreate, TaskFilters, TaskRead, TaskUpdate


class TaskRepository(Protocol):
    def create(self, data: TaskCreate) -> TaskRead: ...

    def get(self, task_id: int) -> TaskRead | None: ...

    def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]: ...

    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None: ...

    def delete(self, task_id: int) -> bool: ...
