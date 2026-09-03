"""Couche métier des projets — conscient de l'acteur (Module 06)."""

from __future__ import annotations

from taskman.core.exceptions import ProjectNotFoundError
from taskman.repositories import ProjectRepository, UnitOfWork
from taskman.schemas import ProjectCreate, ProjectPage, ProjectRead, UserRead, UserRole


class ProjectService:
    def __init__(self, projects: ProjectRepository, uow: UnitOfWork, actor: UserRead) -> None:
        self._projects = projects
        self._uow = uow
        self._actor = actor

    @property
    def _scope(self) -> int | None:
        return None if self._actor.role is UserRole.admin else self._actor.id

    async def create(self, data: ProjectCreate) -> ProjectRead:
        project = await self._projects.create(data, owner_id=self._actor.id)
        await self._uow.commit()
        return project

    async def get(self, project_id: int) -> ProjectRead:
        owner_id = await self._projects.get_owner_id(project_id)
        if owner_id is None or (self._scope is not None and owner_id != self._scope):
            raise ProjectNotFoundError(project_id)
        project = await self._projects.get(project_id)
        assert project is not None
        return project

    async def list(self, *, limit: int, offset: int) -> ProjectPage:
        items, total = await self._projects.list_page(
            owner_id=self._scope, limit=limit, offset=offset
        )
        return ProjectPage(items=items, total=total, limit=limit, offset=offset)
