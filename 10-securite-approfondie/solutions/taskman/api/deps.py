"""Dépendances injectables.

Module 06 : la chaîne d'authentification.

    Authorization: Bearer <access_token>
            │
      oauth2_scheme  (extrait le token de l'entête)
            │ Depends
      get_current_user  (décode le token, charge l'utilisateur)  ─▶ UserRead
            │ Depends
      get_task_service(repo, session, user)  ─▶ TaskService(actor=user)

`require_role(...)` : dépendance de route pour le contrôle d'accès basé sur les rôles.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.core.cache import Cache
from taskman.core.config import Settings, get_settings
from taskman.core.exceptions import PermissionDeniedError
from taskman.db.session import get_session
from taskman.repositories import (
    ProjectRepository,
    RefreshTokenRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyTaskRepository,
    SqlAlchemyUserRepository,
    TaskRepository,
    UserRepository,
)
from taskman.schemas import UserRead, UserRole
from taskman.services import AuthService, ProjectService, TaskService
from taskman.services.notifications import LoggingNotifier, Notifier

# `tokenUrl` sert à la doc (bouton « Authorize » de Swagger). L'extraction, elle,
# ne lit que l'entête `Authorization: Bearer ...`.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_cache(request: Request) -> Cache:
    cache: Cache = request.app.state.cache
    return cache


def get_notifier() -> Notifier:
    return LoggingNotifier()


CacheDep = Annotated[Cache, Depends(get_cache)]
NotifierDep = Annotated[Notifier, Depends(get_notifier)]


# --- repositories --------------------------------------------------------
def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return SqlAlchemyProjectRepository(session)


def get_user_repository(session: SessionDep) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_refresh_token_repository(session: SessionDep) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


# --- services ---------------------------------------------------------
def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_tokens: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
    session: SessionDep,
    settings: SettingsDep,
) -> AuthService:
    return AuthService(users, refresh_tokens, uow=session, settings=settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# --- utilisateur courant ---------------------------------------------
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth: AuthServiceDep,
) -> UserRead:
    user = await auth.user_from_access_token(token)
    return UserRead.model_validate(user)


CurrentUser = Annotated[UserRead, Depends(get_current_user)]


def require_role(
    *allowed: UserRole,
) -> Callable[[UserRead], Coroutine[Any, Any, UserRead]]:
    async def _dependency(user: CurrentUser) -> UserRead:
        if user.role not in allowed:
            raise PermissionDeniedError(f"Rôle requis : {' ou '.join(r.value for r in allowed)}")
        return user

    return _dependency


# --- services métier (dépendent de l'utilisateur courant) ------------
def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
    session: SessionDep,
    user: CurrentUser,
    cache: CacheDep,
) -> TaskService:
    return TaskService(tasks, uow=session, actor=user, cache=cache)


def get_project_service(
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
    session: SessionDep,
    user: CurrentUser,
) -> ProjectService:
    return ProjectService(projects, uow=session, actor=user)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
