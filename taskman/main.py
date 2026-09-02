"""Application FastAPI de taskman.

Module 01 : CRUD `tasks` en mémoire. Lancer :  fastapi dev taskman/main.py
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Response, status

from taskman import __version__
from taskman.models import Task, TaskCreate, TaskPage, TaskStatus, TaskUpdate
from taskman.store import InMemoryTaskStore

app = FastAPI(
    title="taskman",
    version=__version__,
    summary="API de gestion de tâches — projet fil rouge du cursus Backend-Python",
)

store = InMemoryTaskStore()

TaskId = Annotated[int, Path(ge=1, description="Identifiant de la tâche")]


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "taskman", "version": __version__, "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks", status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate, response: Response) -> Task:
    task = store.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@app.get("/tasks", tags=["tasks"])
def list_tasks(
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    min_priority: Annotated[int | None, Query(ge=1, le=5)] = None,
    sort: Annotated[
        Literal["priority", "-priority", "created_at", "-created_at"], Query()
    ] = "-priority",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TaskPage:
    items, total = store.list(
        status=status_filter,
        min_priority=min_priority,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return TaskPage(items=items, total=total, limit=limit, offset=offset)


@app.get("/tasks/{task_id}", tags=["tasks"])
def get_task(task_id: TaskId) -> Task:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}", tags=["tasks"])
def update_task(task_id: TaskId, changes: TaskUpdate) -> Task:
    task = store.update(task_id, changes)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: TaskId) -> Response:
    if not store.delete(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
