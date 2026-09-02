"""Application FastAPI de taskman.

Module 02 : contrats d'entrée/sortie séparés, PATCH correct, types riches,
query model pour les filtres, exemples OpenAPI.
Lancer :  fastapi dev taskman/main.py
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Path, Query, Response, status

from .models import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate
from .store import InMemoryTaskStore

app = FastAPI(
    title="taskman",
    version="0.2.0",
    summary="API de gestion de tâches — projet fil rouge du cursus Backend-Python",
    # True (défaut) : OpenAPI expose des schémas -Input/-Output distincts,
    # ce qui aide les générateurs de SDK. On garde le défaut.
    separate_input_output_schemas=True,
)

store = InMemoryTaskStore()

TaskId = Annotated[int, Path(ge=1, description="Identifiant de la tâche")]

_CREATE_EXAMPLES = {
    "minimal": {
        "summary": "Minimal (champs requis seulement)",
        "value": {"title": "Acheter du café pour l'équipe", "project_id": 1},
    },
    "complet": {
        "summary": "Tous les champs",
        "value": {
            "title": "Préparer la release 0.2",
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


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "taskman", "version": "0.2.0", "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks", status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(
    payload: Annotated[TaskCreate, Body(openapi_examples=_CREATE_EXAMPLES)],
    response: Response,
) -> TaskRead:
    task = store.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@app.get("/tasks", tags=["tasks"])
def list_tasks(filters: Annotated[TaskFilters, Query()]) -> TaskPage:
    items, total = store.list(filters)
    return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)


@app.get("/tasks/{task_id}", tags=["tasks"])
def get_task(task_id: TaskId) -> TaskRead:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}", tags=["tasks"])
def update_task(task_id: TaskId, changes: TaskUpdate) -> TaskRead:
    task = store.update(task_id, changes)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: TaskId) -> Response:
    if not store.delete(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
