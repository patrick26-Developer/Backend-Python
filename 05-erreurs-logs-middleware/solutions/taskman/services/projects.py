"""Couche métier des projets."""

from __future__ import annotations

from taskman.core.exceptions import ProjectNotFoundError
from taskman.repositories import ProjectRepository, UnitOfWork
from taskman.schemas import ProjectCreate, ProjectPage, ProjectRead


class ProjectService:
    def __init__(self, projects: ProjectRepository, uow: UnitOfWork) -> None:
        self._projects = projects
        self._uow = uow

    async def create(self, data: ProjectCreate) -> ProjectRead:
        project = await self._projects.create(data)
        await self._uow.commit()
        return project

    async def get(self, project_id: int) -> ProjectRead:
        project = await self._projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    async def list(self, *, limit: int, offset: int) -> ProjectPage:
        items, total = await self._projects.list(limit=limit, offset=offset)
        return ProjectPage(items=items, total=total, limit=limit, offset=offset)
