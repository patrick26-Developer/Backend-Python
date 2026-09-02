"""Routes HTTP des projets. Le « pas trouvé » est géré par le service + handler central."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from taskman.api.deps import ProjectServiceDep
from taskman.schemas import ProjectCreate, ProjectPage, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])

ProjectId = Annotated[int, Path(ge=1)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, service: ProjectServiceDep, response: Response
) -> ProjectRead:
    project = await service.create(payload)
    response.headers["Location"] = f"/projects/{project.id}"
    return project


@router.get("")
async def list_projects(
    service: ProjectServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectPage:
    return await service.list(limit=limit, offset=offset)


@router.get("/{project_id}")
async def get_project(project_id: ProjectId, service: ProjectServiceDep) -> ProjectRead:
    return await service.get(project_id)
