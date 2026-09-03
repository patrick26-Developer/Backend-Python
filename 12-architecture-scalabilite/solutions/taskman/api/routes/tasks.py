"""Routes HTTP des tâches.

Ordre important : `/tasks/export` (littéral) est déclaré **avant** `/tasks/{task_id}`
(paramétré) — sinon FastAPI tenterait de convertir "export" en `int` et renverrait 422.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Path, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from taskman.api.deps import NotifierDep, TaskServiceDep
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
            "title": "Préparer la release 0.8",
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
    request: Request,
    response: Response,
) -> TaskRead:
    task = await service.create(payload)
    # url_for résout le chemin complet (préfixe /v1 + root_path éventuel).
    response.headers["Location"] = request.url_for("get_task", task_id=task.id).path
    return task


@router.get("")
async def list_tasks(
    filters: Annotated[TaskFilters, Query()],
    service: TaskServiceDep,
) -> TaskPage:
    return await service.list(filters)


@router.get("/export")
async def export_tasks(service: TaskServiceDep) -> StreamingResponse:
    """Export NDJSON streamé (un objet JSON par ligne) — mémoire constante."""

    async def _lines() -> AsyncIterator[bytes]:
        async for task in service.export():
            yield (task.model_dump_json() + "\n").encode()

    return StreamingResponse(_lines(), media_type="application/x-ndjson")


@router.get("/{task_id}")
async def get_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    return await service.get(task_id)


@router.patch("/{task_id}")
async def update_task(task_id: TaskId, changes: TaskUpdate, service: TaskServiceDep) -> TaskRead:
    return await service.update(task_id, changes)


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: TaskId,
    service: TaskServiceDep,
    notifier: NotifierDep,
    background: BackgroundTasks,
) -> TaskRead:
    task = await service.complete(task_id)
    # notification NON critique -> tâche de fond, exécutée après l'envoi de la réponse.
    background.add_task(notifier.task_completed, task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: TaskId, service: TaskServiceDep) -> Response:
    await service.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
