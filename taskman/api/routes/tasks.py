"""Routes HTTP des tâches.

Rôle de cette couche : **traduire HTTP ↔ service**. Rien d'autre.
- pas de logique métier ici ;
- pas d'accès aux données ici ;
- juste : lire la requête, appeler le service, mapper le résultat sur un code HTTP.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Query, Response, status

from taskman.api.deps import TaskServiceDep
from taskman.schemas import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

TaskId = Annotated[int, Path(ge=1, description="Identifiant de la tâche")]

_CREATE_EXAMPLES = {
    "minimal": {
        "summary": "Minimal (champs requis seulement)",
        "value": {"title": "Acheter du café pour l'équipe", "project_id": 1},
    },
    "complet": {
        "summary": "Tous les champs",
        "value": {
            "title": "Préparer la release 0.3",
            "project_id": 1,
            "description": "Changelog, tag, migration",
            "priority": 5,
            "due_date": "2026-12-31T17:00:00Z",
            "tags": ["release", "ops"],
            "assignee_email": "dev@exemple.org",
            "estimate_hours": "4.00",
            "checklist": [{"label": "Écrire le changelog"}, {"label": "Taguer la version"}],
        },
    },
}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: Annotated[TaskCreate, Body(openapi_examples=_CREATE_EXAMPLES)],
    service: TaskServiceDep,
    response: Response,
) -> TaskRead:
    task = service.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@router.get("")
def list_tasks(
    filters: Annotated[TaskFilters, Query()],
    service: TaskServiceDep,
) -> TaskPage:
    return service.list(filters)


@router.get("/{task_id}")
def get_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    task = service.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}")
def update_task(task_id: TaskId, changes: TaskUpdate, service: TaskServiceDep) -> TaskRead:
    task = service.update(task_id, changes)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: TaskId, service: TaskServiceDep) -> Response:
    if not service.delete(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
