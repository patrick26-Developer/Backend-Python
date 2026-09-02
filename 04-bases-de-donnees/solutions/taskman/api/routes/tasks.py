"""Routes HTTP des tâches. Traduit HTTP ↔ service. Async depuis le Module 04."""

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
            "title": "Préparer la release 0.4",
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
async def create_task(
    payload: Annotated[TaskCreate, Body(openapi_examples=_CREATE_EXAMPLES)],
    service: TaskServiceDep,
    response: Response,
) -> TaskRead:
    task = await service.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@router.get("")
async def list_tasks(
    filters: Annotated[TaskFilters, Query()],
    service: TaskServiceDep,
) -> TaskPage:
    return await service.list(filters)


@router.get("/{task_id}")
async def get_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    task = await service.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}")
async def update_task(task_id: TaskId, changes: TaskUpdate, service: TaskServiceDep) -> TaskRead:
    task = await service.update(task_id, changes)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: TaskId, service: TaskServiceDep) -> Response:
    if not await service.delete(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
