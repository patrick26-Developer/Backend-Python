"""Solution Module 01 — API `taskman`, CRUD complet en mémoire.

Lancer :  fastapi dev 01-fondations-http-et-fastapi/solutions/main.py
Docs   :  http://127.0.0.1:8000/docs

Ce que ce fichier illustre :
- routes fines : elles traduisent HTTP <-> store, rien de plus ;
- codes de statut explicites (201, 204) ;
- 404 propre via HTTPException (remplacé par un handler central au Module 05) ;
- `response_model` implicite via l'annotation de retour ;
- validation des query params avec Annotated + Query.

Ce qu'il NE fait volontairement pas encore : couches séparées formelles,
injection de dépendances, base de données, auth. Chaque chose en son module.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Response, status

from .models import Task, TaskCreate, TaskPage, TaskStatus, TaskUpdate
from .store import InMemoryTaskStore

app = FastAPI(
    title="taskman",
    version="0.1.0",
    summary="API de gestion de tâches — Module 01 (fondations)",
)

# Échafaudage : un store global. Au Module 03 il passe derrière `Depends`.
store = InMemoryTaskStore()


# ---------------------------------------------------------------------------
# Métadonnées de service
# ---------------------------------------------------------------------------
@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "taskman", "version": "0.1.0", "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Bac à sable (exercice 01.2) — à retirer une fois compris
# ---------------------------------------------------------------------------
@app.get("/echo/{item_id}", tags=["playground"])
def echo(
    item_id: Annotated[int, Path(ge=1)],
    q: Annotated[str | None, Query(max_length=50)] = None,
    verbose: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    payload: dict[str, object] = {"item_id": item_id, "q": q, "verbose": verbose}
    if verbose:
        payload["length"] = len(q) if q else 0
    return payload


# ---------------------------------------------------------------------------
# CRUD tasks
# ---------------------------------------------------------------------------
TaskId = Annotated[int, Path(ge=1, description="Identifiant de la tâche")]


@app.post("/tasks", status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate, response: Response) -> Task:
    task = store.create(payload)
    # En-tête Location : convention REST, pointe vers la ressource créée.
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
    # Choix de design : 2e DELETE -> 404. On considère "supprimer une ressource
    # déjà absente" comme une erreur du client (il croyait qu'elle existait).
    # 204 serait aussi défendable (idempotence stricte). Documenté, donc assumé.
    if not store.delete(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
