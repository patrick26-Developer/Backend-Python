"""Dépendances injectables (Module 04 : adossées à une session de base de données).

Graphe résolu par FastAPI pour une requête sur les tâches :

    route ──▶ get_task_service
                 ├─ Depends ─▶ get_task_repository ─▶ get_session
                 └─ Depends ─▶ get_session

`get_session` est demandé deux fois mais FastAPI **met en cache** les
sous-dépendances dans une requête : le repository et le service partagent donc
LA MÊME session. `get_session` (dans `taskman/db/session.py`) est une dépendance
`yield` : elle ouvre la session, la fournit, la ferme à la fin de la requête.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.core.config import Settings, get_settings
from taskman.db.session import get_session
from taskman.repositories import (
    ProjectRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyTaskRepository,
    TaskRepository,
)
from taskman.services import ProjectService, TaskService

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)


def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
    session: SessionDep,
) -> TaskService:
    return TaskService(tasks, uow=session)


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return SqlAlchemyProjectRepository(session)


def get_project_service(
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
    session: SessionDep,
) -> ProjectService:
    return ProjectService(projects, uow=session)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
