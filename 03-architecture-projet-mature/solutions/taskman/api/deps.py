"""Dépendances injectables partagées par les routes.

Le graphe de dépendances (résolu automatiquement par FastAPI) :

    route ── Depends ──▶ get_task_service
                              │ Depends
                              ▼
                        get_task_repository ──▶ request.app.state.task_repository
                              (créé au démarrage — voir taskman/main.py lifespan)

En test, on remplace un maillon via `app.dependency_overrides` (voir tests/conftest.py).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from taskman.core.config import Settings, get_settings
from taskman.repositories import TaskRepository
from taskman.services import TaskService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_task_repository(request: Request) -> TaskRepository:
    """Le repository vit dans `app.state`, créé au démarrage de l'app."""
    repo: TaskRepository = request.app.state.task_repository
    return repo


def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(tasks)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
