"""Couche métier des tâches.

Le service orchestre les règles applicatives et parle au repository. Il ne connaît
**ni HTTP** (`Request`, `HTTPException`, codes de statut) **ni SQL**.

Au Module 03, il est volontairement mince (il délègue) : ce qui compte, c'est la
**couture**. Il se remplit ensuite :
- Module 04 : frontière transactionnelle (commit / rollback) ;
- Module 05 : exceptions métier (`TaskNotFoundError`) au lieu de `None` ;
- Module 06 : contrôle d'accès (« l'utilisateur voit-il cette tâche ? ») ;
- Module 08 : cache, événements.
"""

from __future__ import annotations

from taskman.repositories import TaskRepository
from taskman.schemas import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate


class TaskService:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    def create(self, data: TaskCreate) -> TaskRead:
        return self._tasks.create(data)

    def get(self, task_id: int) -> TaskRead | None:
        return self._tasks.get(task_id)

    def list(self, filters: TaskFilters) -> TaskPage:
        items, total = self._tasks.list(filters)
        return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)

    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        return self._tasks.update(task_id, changes)

    def delete(self, task_id: int) -> bool:
        return self._tasks.delete(task_id)
